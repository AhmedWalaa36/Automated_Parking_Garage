import sqlite3
import os
import io
import logging
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from PIL import Image, ImageFilter, ImageEnhance
import pytesseract
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SmartGarage")

DB_FILE      = "garage.db"
RATE_PER_HR  = 50.0
TESSERACT    = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pytesseract.pytesseract.tesseract_cmd = TESSERACT

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ==========================================
# PYDANTIC SCHEMAS
# ==========================================

class LoginBody(BaseModel):
    email: str
    password: str

# Flutter sends PascalCase keys for register
class RegisterBody(BaseModel):
    Name: str
    Phone: Optional[str] = ""
    Email: str
    Password: str
    Membership: Optional[str] = "Standard"

# Flutter sends PascalCase keys for add_vehicle
class AddVehicleBody(BaseModel):
    CustomerID: int
    PlateNo: str

# Flutter sends PascalCase keys for update
class UpdateCustomerBody(BaseModel):
    Name: Optional[str] = None
    Phone: Optional[str] = None
    Email: Optional[str] = None
    Password: Optional[str] = None
    Membership: Optional[str] = None

# Flutter sends snake_case for parking actions
class StartParkingBody(BaseModel):
    vehicle_id: int
    spot_id: int

class RetrieveCarBody(BaseModel):
    vehicle_id: int



# ESP32 hardware schemas
class HardwareParkedBody(BaseModel):
    plate_no: str
    spot_code: str

class HardwareRetrievedBody(BaseModel):
    spot_code: str

class AdminAddCustomerBody(BaseModel):
    name: str
    plate_no: str
    phone: Optional[str] = ""
    pin: Optional[str] = "1234"


# ==========================================
# DATABASE HELPERS
# ==========================================

def db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Customers (
                CustomerID INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL,
                Phone TEXT,
                Email TEXT UNIQUE NOT NULL,
                Password TEXT NOT NULL,
                Membership TEXT DEFAULT 'Standard'
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Vehicles (
                VehicleID INTEGER PRIMARY KEY AUTOINCREMENT,
                CustomerID INTEGER NOT NULL,
                PlateNo TEXT UNIQUE NOT NULL,
                FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ParkingSpots (
                SpotID INTEGER PRIMARY KEY AUTOINCREMENT,
                SpotCode TEXT UNIQUE NOT NULL,
                Status TEXT DEFAULT 'Free'
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ParkingSessions (
                SessionID INTEGER PRIMARY KEY AUTOINCREMENT,
                VehicleID INTEGER NOT NULL,
                SpotID INTEGER NOT NULL,
                EntryTime TEXT NOT NULL,
                ExitTime TEXT,
                Fee REAL,
                FOREIGN KEY (VehicleID) REFERENCES Vehicles(VehicleID) ON DELETE CASCADE,
                FOREIGN KEY (SpotID) REFERENCES ParkingSpots(SpotID) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Payments (
                PaymentID     INTEGER PRIMARY KEY AUTOINCREMENT,
                SessionID     INTEGER NOT NULL,
                Amount        REAL NOT NULL,
                PaymentMethod TEXT DEFAULT 'Cash',
                PaymentTime   TEXT NOT NULL,
                FOREIGN KEY (SessionID) REFERENCES ParkingSessions(SessionID) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Logs (
                LogID     INTEGER PRIMARY KEY AUTOINCREMENT,
                Event     TEXT NOT NULL,
                EventType TEXT DEFAULT 'INFO',
                Source    TEXT,
                Time      TEXT NOT NULL
            );
        """)


        spots_count = conn.execute("SELECT COUNT(*) as cnt FROM ParkingSpots").fetchone()["cnt"]
        if spots_count == 0:
            for i in range(1, 13):
                conn.execute("INSERT INTO ParkingSpots (SpotCode, Status) VALUES (?, 'Free')", (f"PL.{i}",))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to initialize database: {str(e)}")
        raise
    finally:
        conn.close()


def extract_plate(image_bytes: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        img = ImageEnhance.Contrast(img).enhance(2.5)
        img = img.filter(ImageFilter.SHARPEN)
        w, h = img.size
        if w < 640:
            img = img.resize((w * 2, h * 2), Image.LANCZOS)
        raw = pytesseract.image_to_string(
            img,
            config="--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )
        return "".join(raw.split()).upper()
    except Exception as e:
        logger.error(f"OCR Error processing image: {str(e)}")
        return ""


def calc_fee(entry_time: str) -> tuple[int, float]:
    entry   = datetime.fromisoformat(entry_time)
    minutes = int((datetime.now() - entry).total_seconds() / 60)
    fee     = round((minutes / 60.0) * RATE_PER_HR, 2)
    return minutes, fee


# ==========================================
# ESP32 HARDWARE ENDPOINTS
# ==========================================

@app.post("/entry")
async def car_entry(request: Request):
    logger.info("Received entry request from hardware camera.")
    image_bytes = await request.body()
    if not image_bytes:
        logger.warning("Entry request contains empty body.")
        raise HTTPException(400, "No image data received")

    plate = extract_plate(image_bytes)
    if not plate:
        logger.warning("OCR Engine failed to recognize any characters from plate.")
        raise HTTPException(422, "Could not read plate — check lighting and camera angle")

    logger.info(f"OCR successfully extracted Plate: {plate}")
    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        vehicle = conn.execute(
            "SELECT v.*, c.Name FROM Vehicles v JOIN Customers c ON v.CustomerID = c.CustomerID WHERE v.PlateNo=?",
            (plate,)
        ).fetchone()

        if not vehicle:
            logger.warning(f"Plate {plate} is not registered in system.")
            raise HTTPException(404, f"Plate {plate} is not registered")

        already_parked = conn.execute(
            "SELECT SessionID FROM ParkingSessions WHERE VehicleID=? AND ExitTime IS NULL",
            (vehicle["VehicleID"],)
        ).fetchone()

        if already_parked:
            logger.warning(f"Vehicle with Plate {plate} is already actively parked.")
            raise HTTPException(409, "This vehicle already has an active session")

        conn.commit()
        logger.info(f"Entry processed successfully for Plate: {plate}, Customer: {vehicle['Name']}")
        conn.execute(
            "INSERT INTO Logs (Event, EventType, Source, Time) VALUES (?,?,?,?)"
            , (f"Vehicle entry detected, Plate={plate}, Customer={vehicle['Name']}", "INFO", "CAMERA", datetime.now().isoformat())
        )
        conn.commit()
        return {"status": "ok", "plate": plate, "customer": vehicle["Name"]}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during /entry processing: {str(e)}")
        raise HTTPException(500, str(e))
    finally:
        conn.close()





@app.post("/parked")
def car_parked(body: HardwareParkedBody):
    plate     = body.plate_no.upper()
    spot_code = body.spot_code

    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        vehicle = conn.execute("SELECT VehicleID FROM Vehicles WHERE PlateNo=?", (plate,)).fetchone()
        spot = conn.execute("SELECT SpotID, Status FROM ParkingSpots WHERE SpotCode=?", (spot_code,)).fetchone()

        if not vehicle or not spot:
            raise HTTPException(404, "Vehicle or Spot matching hardware data not found")

        if spot["Status"] != "Free":
            raise HTTPException(409, "Target parking spot is already occupied")

        already_parked = conn.execute(
            "SELECT SessionID FROM ParkingSessions WHERE VehicleID=? AND ExitTime IS NULL",
            (vehicle["VehicleID"],)
        ).fetchone()

        if already_parked:
            raise HTTPException(409, "Vehicle already parked in another session")

        conn.execute(
            "INSERT INTO ParkingSessions (VehicleID, SpotID, EntryTime) VALUES (?,?,?)",
            (vehicle["VehicleID"], spot["SpotID"], datetime.now().isoformat())
        )
        conn.execute("UPDATE ParkingSpots SET Status='Occupied' WHERE SpotID=?", (spot["SpotID"],))
        conn.commit()
        logger.info(f"Parking complete: Plate {plate} successfully parked at Spot {spot_code}")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error executing /parked: {str(e)}")
        raise HTTPException(500, str(e))
    finally:
        conn.close()


@app.post("/retrieved")
def car_retrieved(body: HardwareRetrievedBody):
    spot_code = body.spot_code

    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        session = conn.execute(
            """SELECT ps.* FROM ParkingSessions ps
               JOIN ParkingSpots p ON ps.SpotID = p.SpotID
               WHERE p.SpotCode=? AND ps.ExitTime IS NULL""",
            (spot_code,)
        ).fetchone()

        if not session:
            conn.commit()
            return {"status": "ok", "note": "session already closed"}

        minutes, fee = calc_fee(session["EntryTime"])

        conn.execute(
            "UPDATE ParkingSessions SET ExitTime=?, Fee=? WHERE SessionID=?",
            (datetime.now().isoformat(), fee, session["SessionID"])
        )
        conn.execute("UPDATE ParkingSpots SET Status='Free' WHERE SpotID=?", (session["SpotID"],))
        conn.commit()
        logger.info(f"Retrieval complete: Vehicle from Spot {spot_code} retrieved successfully.")
        return {"status": "ok", "fee": fee, "duration_min": minutes}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inside /retrieved endpoint: {str(e)}")
        raise HTTPException(500, str(e))
    finally:
        conn.close()


# ==========================================
# FLUTTER CLIENT API ENDPOINTS
# ==========================================

@app.post("/login")
def login(body: LoginBody):
    """
    Flutter sends:  { "email": "...", "password": "..." }
    Flutter expects: { "user": { "CustomerID": 1, "Name": "...", "Phone": "...", "Email": "...", "Membership": "..." } }
    """
    email    = body.email.strip()
    password = body.password

    conn = db()
    try:
        customer = conn.execute(
            "SELECT * FROM Customers WHERE Email=? AND Password=?", (email, password)
        ).fetchone()

        if not customer:
            raise HTTPException(401, "Incorrect credentials")

        return {
            "user": {
                "CustomerID": customer["CustomerID"],
                "Name":       customer["Name"],
                "Phone":      customer["Phone"],
                "Email":      customer["Email"],
                "Membership": customer["Membership"]
            }
        }
    finally:
        conn.close()


@app.post("/register")
def register(body: RegisterBody):
    """
    Flutter sends:  { "Name": "...", "Phone": "...", "Email": "...", "Password": "...", "Membership": "standard" }
    Flutter expects: { "CustomerID": 1 }
    """
    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        cursor = conn.execute(
            "INSERT INTO Customers (Name, Phone, Email, Password, Membership) VALUES (?,?,?,?,?)",
            (body.Name, body.Phone, body.Email, body.Password, body.Membership)
        )
        customer_id = cursor.lastrowid
        conn.commit()
        return {"CustomerID": customer_id}
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(409, "Email is already registered")
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()


@app.post("/add_vehicle")
def add_vehicle(body: AddVehicleBody):
    """
    Flutter sends:  { "CustomerID": 1, "PlateNo": "ABC123" }
    Flutter expects: { "VehicleID": 1 }
    """
    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        cursor = conn.execute(
            "INSERT INTO Vehicles (CustomerID, PlateNo) VALUES (?,?)",
            (body.CustomerID, body.PlateNo.upper())
        )
        vehicle_id = cursor.lastrowid
        conn.commit()
        return {"VehicleID": vehicle_id}
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(409, "Vehicle plate number already registered")
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()


@app.get("/customer/{id}")
def get_customer(id: int):
    """
    Flutter expects: { "CustomerID": 1, "Name": "...", "Phone": "...", "Email": "...", "Password": "...", "Membership": "..." }
    Note: Password is included because ProfileScreen reads it to pre-fill the edit dialog.
    """
    conn = db()
    try:
        customer = conn.execute("SELECT * FROM Customers WHERE CustomerID=?", (id,)).fetchone()
        if not customer:
            raise HTTPException(404, "Customer not found")
        return {
            "CustomerID": customer["CustomerID"],
            "Name":       customer["Name"],
            "Phone":      customer["Phone"],
            "Email":      customer["Email"],
            "Password":   customer["Password"],
            "Membership": customer["Membership"]
        }
    finally:
        conn.close()


@app.put("/customer/{id}")
def update_customer(id: int, body: UpdateCustomerBody):
    """
    Flutter sends: { "Name": "...", "Phone": "...", "Email": "...", "Password": "..." }
    Flutter expects: 200 status (return value is ignored)
    """
    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        customer = conn.execute("SELECT * FROM Customers WHERE CustomerID=?", (id,)).fetchone()
        if not customer:
            raise HTTPException(404, "Customer not found")

        name       = body.Name       if body.Name       is not None else customer["Name"]
        phone      = body.Phone      if body.Phone      is not None else customer["Phone"]
        email      = body.Email      if body.Email      is not None else customer["Email"]
        password   = body.Password   if body.Password   is not None else customer["Password"]
        membership = body.Membership if body.Membership is not None else customer["Membership"]

        conn.execute(
            "UPDATE Customers SET Name=?, Phone=?, Email=?, Password=?, Membership=? WHERE CustomerID=?",
            (name, phone, email, password, membership, id)
        )
        conn.commit()
        return {"status": "ok"}
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(409, "Email conflicts with an existing customer account")
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()


@app.delete("/customer/{id}")
def delete_customer_endpoint(id: int):
    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        customer = conn.execute("SELECT * FROM Customers WHERE CustomerID=?", (id,)).fetchone()
        if not customer:
            raise HTTPException(404, "Customer not found")
        conn.execute("DELETE FROM Customers WHERE CustomerID=?", (id,))
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()


@app.get("/customer/{id}/vehicles")
def get_customer_vehicles(id: int):
    """
    Flutter expects list of: { "VehicleID": 1, "CustomerID": 1, "PlateNo": "..." }
    Flutter reads: vehicle['VehicleID'], vehicle['PlateNo']
    """
    conn = db()
    try:
        vehicles = conn.execute("SELECT * FROM Vehicles WHERE CustomerID=?", (id,)).fetchall()
        return [
            {
                "VehicleID":  v["VehicleID"],
                "CustomerID": v["CustomerID"],
                "PlateNo":    v["PlateNo"]
            }
            for v in vehicles
        ]
    finally:
        conn.close()


@app.get("/customer/{id}/sessions")
def get_customer_sessions(id: int):
    """
    Flutter expects list of:
    { "SessionID": 1, "PlateNo": "...", "SpotCode": "...", "EntryTime": "...", "ExitTime": null or "...", "Fee": 0 }
    Flutter checks: s['ExitTime'] != null  → must be null (not "") for open sessions
    Flutter reads: s['PlateNo'], s['SpotCode'], s['EntryTime'], s['ExitTime'], s['Fee']
    """
    conn = db()
    try:
        sessions = conn.execute(
            """SELECT ps.SessionID, ps.VehicleID, ps.SpotID, ps.EntryTime, ps.ExitTime, ps.Fee,
                      v.PlateNo, spot.SpotCode
               FROM ParkingSessions ps
               JOIN Vehicles v    ON ps.VehicleID = v.VehicleID
               JOIN ParkingSpots spot ON ps.SpotID = spot.SpotID
               WHERE v.CustomerID=?
               ORDER BY ps.EntryTime DESC""",
            (id,)
        ).fetchall()

        result = []
        for s in sessions:
            result.append({
                "SessionID": s["SessionID"],
                "VehicleID": s["VehicleID"],
                "SpotID":    s["SpotID"],
                "PlateNo":   s["PlateNo"],
                "SpotCode":  s["SpotCode"],
                "EntryTime": s["EntryTime"],
                "ExitTime":  s["ExitTime"],          # null when still parked — Flutter checks != null
                "Fee":       s["Fee"] if s["Fee"] is not None else 0
            })
        return result
    finally:
        conn.close()


@app.get("/available_spots")
def get_available_spots():
    """
    Flutter expects list of: { "SpotID": 1, "SpotCode": "PL.1", "Status": "Free" }
    """
    conn = db()
    try:
        spots = conn.execute("SELECT * FROM ParkingSpots WHERE Status='Free'").fetchall()
        return [
            {
                "SpotID":   s["SpotID"],
                "SpotCode": s["SpotCode"],
                "Status":   s["Status"]
            }
            for s in spots
        ]
    finally:
        conn.close()


@app.post("/start_parking")
def start_parking(body: StartParkingBody):
    """
    Flutter sends:  { "vehicle_id": 1, "spot_id": 1 }
    Flutter expects: { "SessionID": 1 }
    """
    vehicle_id = body.vehicle_id
    spot_id    = body.spot_id

    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        spot = conn.execute(
            "SELECT * FROM ParkingSpots WHERE SpotID=? AND Status='Free'", (spot_id,)
        ).fetchone()
        if not spot:
            raise HTTPException(400, "Spot is busy or does not exist")

        already_parked = conn.execute(
            "SELECT SessionID FROM ParkingSessions WHERE VehicleID=? AND ExitTime IS NULL", (vehicle_id,)
        ).fetchone()
        if already_parked:
            raise HTTPException(409, "Vehicle already parked in another session")

        cursor = conn.execute(
            "INSERT INTO ParkingSessions (VehicleID, SpotID, EntryTime) VALUES (?,?,?)",
            (vehicle_id, spot_id, datetime.now().isoformat())
        )
        session_id = cursor.lastrowid
        conn.execute("UPDATE ParkingSpots SET Status='Occupied' WHERE SpotID=?", (spot_id,))
        conn.commit()
        return {"SessionID": session_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()


@app.post("/retrieve_car")
def request_retrieve_car(body: RetrieveCarBody):
    """
    Flutter sends:  { "vehicle_id": 1 }
    Flutter expects full session data for PaymentScreen:
    { "SessionID": 1, "PlateNo": "...", "SpotCode": "...", "EntryTime": "...", "ExitTime": "...", "Fee": 25.0 }

    This endpoint:
    1. Finds the active session
    2. Closes it immediately (sets ExitTime + Fee) so Flutter can show the payment screen
    3. Queues a hardware retrieve command for the ESP32
    4. Returns full session data
    """
    vehicle_id = body.vehicle_id
    logger.info(f"Retrieve request issued for VehicleID: {vehicle_id}")

    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE;")

        session = conn.execute(
            """SELECT ps.SessionID, ps.VehicleID, ps.SpotID, ps.EntryTime,
                      s.SpotCode, v.PlateNo
               FROM ParkingSessions ps
               JOIN ParkingSpots s ON ps.SpotID = s.SpotID
               JOIN Vehicles v     ON ps.VehicleID = v.VehicleID
               WHERE ps.VehicleID=? AND ps.ExitTime IS NULL""",
            (vehicle_id,)
        ).fetchone()

        if not session:
            logger.warning(f"No active session for retrieval of VehicleID {vehicle_id}")
            raise HTTPException(404, "No active parking session found for this vehicle")

        exit_time = datetime.now().isoformat()
        minutes, fee = calc_fee(session["EntryTime"])

        # Close the session immediately so Flutter can show payment
        conn.execute(
            "UPDATE ParkingSessions SET ExitTime=?, Fee=? WHERE SessionID=?",
            (exit_time, fee, session["SessionID"])
        )
        conn.execute(
            "UPDATE ParkingSpots SET Status='Free' WHERE SpotID=?",
            (session["SpotID"],)
        )

        conn.commit()
        logger.info(f"Retrieve complete for VehicleID {vehicle_id}, Spot {session['SpotCode']}, Fee: {fee} EGP")

        # Return full session data that Flutter's PaymentScreen needs
        return {
            "SessionID": session["SessionID"],
            "VehicleID": session["VehicleID"],
            "SpotID":    session["SpotID"],
            "PlateNo":   session["PlateNo"],
            "SpotCode":  session["SpotCode"],
            "EntryTime": session["EntryTime"],
            "ExitTime":  exit_time,
            "Fee":       fee,
            "DurationMin": minutes
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error implementing /retrieve_car: {str(e)}")
        raise HTTPException(500, str(e))
    finally:
        conn.close()





@app.get("/vehicle/{id}/current_status")
def get_vehicle_status(id: int):
    """
    Flutter checks: status != null  → return 404 when not parked so DBHelper returns null
    Flutter reads (when parked): status['SpotCode']
    """
    conn = db()
    try:
        session = conn.execute(
            """SELECT ps.*, s.SpotCode FROM ParkingSessions ps
               JOIN ParkingSpots s ON ps.SpotID = s.SpotID
               WHERE ps.VehicleID=? AND ps.ExitTime IS NULL""",
            (id,)
        ).fetchone()

        if not session:
            # Return 404 so DBHelper returns null → Flutter shows "Not Parked"
            raise HTTPException(404, "Vehicle is not currently parked")

        minutes, fee = calc_fee(session["EntryTime"])
        return {
            "SessionID":   session["SessionID"],
            "SpotCode":    session["SpotCode"],
            "EntryTime":   session["EntryTime"],
            "Fee":         fee,
            "DurationMin": minutes
        }
    finally:
        conn.close()


@app.get("/vehicle/{id}/latest_open_session")
def latest_open_session(id: int):
    """
    Flutter expects: { "SessionID": 1, "VehicleID": 1, "SpotID": 1, "EntryTime": "...", "ExitTime": null, "Fee": 0 }
    """
    conn = db()
    try:
        session = conn.execute(
            "SELECT * FROM ParkingSessions WHERE VehicleID=? AND ExitTime IS NULL ORDER BY SessionID DESC LIMIT 1",
            (id,)
        ).fetchone()
        if not session:
            raise HTTPException(404, "No open session found for this vehicle")
        return {
            "SessionID": session["SessionID"],
            "VehicleID": session["VehicleID"],
            "SpotID":    session["SpotID"],
            "EntryTime": session["EntryTime"],
            "ExitTime":  session["ExitTime"],   # null when still open
            "Fee":       session["Fee"] if session["Fee"] is not None else 0
        }
    finally:
        conn.close()


@app.get("/session/{plate_no}")
def get_session(plate_no: str):
    conn = db()
    try:
        session = conn.execute(
            """SELECT ps.*, v.PlateNo, c.Name as CustomerName, s.SpotCode FROM ParkingSessions ps
               JOIN Vehicles v ON ps.VehicleID = v.VehicleID
               JOIN Customers c ON v.CustomerID = c.CustomerID
               JOIN ParkingSpots s ON ps.SpotID = s.SpotID
               WHERE v.PlateNo=? AND ps.ExitTime IS NULL""",
            (plate_no.upper(),)
        ).fetchone()

        if not session:
            return {"active": False}

        minutes, fee = calc_fee(session["EntryTime"])
        return {
            "active":        True,
            "SessionID":     session["SessionID"],
            "session_id":    session["SessionID"],
            "SpotCode":      session["SpotCode"],
            "spot_code":     session["SpotCode"],
            "CustomerName":  session["CustomerName"],
            "customer_name": session["CustomerName"],
            "EntryTime":     session["EntryTime"],
            "entry_time":    session["EntryTime"],
            "DurationMin":   minutes,
            "duration_min":  minutes,
            "fee":           fee
        }
    finally:
        conn.close()


# ==========================================
# ADMIN PANEL LOGIC & HTML
# ==========================================

@app.get("/api/admin/data")
def admin_data():
    conn = db()
    try:
        raw_sessions = conn.execute(
            """SELECT ps.SessionID as id, v.PlateNo as plate_no, c.Name as customer_name,
                      spot.SpotCode as spot_code, ps.EntryTime as entry_time, ps.ExitTime as exit_time,
                      ps.Fee as fee, CASE WHEN ps.ExitTime IS NULL THEN 'active' ELSE 'completed' END as status
               FROM ParkingSessions ps
               JOIN Vehicles v ON ps.VehicleID = v.VehicleID
               JOIN Customers c ON v.CustomerID = c.CustomerID
               ORDER BY ps.EntryTime DESC LIMIT 50"""
        ).fetchall()

        sessions_list = []
        for s in raw_sessions:
            item = dict(s)
            if s["exit_time"]:
                entry_dt = datetime.fromisoformat(s["entry_time"])
                exit_dt  = datetime.fromisoformat(s["exit_time"])
                item["duration_min"] = int((exit_dt - entry_dt).total_seconds() / 60)
            else:
                entry_dt = datetime.fromisoformat(s["entry_time"])
                item["duration_min"] = int((datetime.now() - entry_dt).total_seconds() / 60)
            sessions_list.append(item)

        raw_customers = conn.execute(
            """SELECT c.Name as name, v.PlateNo as plate_no, c.Phone as phone, c.Password as pin
               FROM Customers c
               LEFT JOIN Vehicles v ON c.CustomerID = v.CustomerID"""
        ).fetchall()

        return {
            "sessions":  sessions_list,
            "customers": [dict(c) for c in raw_customers],
            "rate":      RATE_PER_HR
        }
    finally:
        conn.close()


@app.post("/api/admin/add-customer")
def admin_add_customer(body: AdminAddCustomerBody):
    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        cursor = conn.execute(
            "INSERT INTO Customers (Name, Phone, Email, Password) VALUES (?,?,?,?)",
            (body.name, body.phone, f"{body.plate_no}@garage.local", body.pin)
        )
        customer_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO Vehicles (CustomerID, PlateNo) VALUES (?,?)",
            (customer_id, body.plate_no.upper())
        )
        conn.commit()
        return {"status": "ok"}
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(409, "A customer or vehicle with this identifier is already registered")
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()


@app.delete("/api/admin/customer/{plate_no}")
def admin_delete_customer(plate_no: str):
    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        vehicle = conn.execute(
            "SELECT CustomerID FROM Vehicles WHERE PlateNo=?", (plate_no.upper(),)
        ).fetchone()
        if vehicle:
            conn.execute("DELETE FROM Customers WHERE CustomerID=?", (vehicle["CustomerID"],))
            conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()


ADMIN_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Smart Garage — Admin</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e2e8f0; min-height: 100vh; }
  header { background: #1a1d2e; border-bottom: 1px solid #2d3748; padding: 18px 32px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 1.25rem; font-weight: 600; color: #fff; }
  .badge { background: #22c55e20; color: #22c55e; border: 1px solid #22c55e40; padding: 3px 10px; border-radius: 20px; font-size: 0.75rem; }
  .badge.warn { background: #f59e0b20; color: #f59e0b; border-color: #f59e0b40; }
  .container { padding: 24px 32px; display: grid; gap: 24px; }
  .grid-3 { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; }
  .card { background: #1a1d2e; border: 1px solid #2d3748; border-radius: 12px; padding: 20px; }
  .card h2 { font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }
  .stat { font-size: 2rem; font-weight: 700; color: #fff; }
  .stat span { font-size: 1rem; color: #64748b; font-weight: 400; }
  .section { background: #1a1d2e; border: 1px solid #2d3748; border-radius: 12px; overflow: hidden; }
  .section-header { padding: 16px 20px; border-bottom: 1px solid #2d3748; display: flex; justify-content: space-between; align-items: center; }
  .section-header h2 { font-size: 0.95rem; font-weight: 600; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { padding: 10px 16px; text-align: left; color: #64748b; font-weight: 500; border-bottom: 1px solid #2d3748; background: #13151f; }
  td { padding: 12px 16px; border-bottom: 1px solid #1e2233; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #1e2233; }
  .spots-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; padding: 20px; }
  .spot { border-radius: 8px; padding: 12px 8px; text-align: center; font-size: 0.8rem; font-weight: 600; }
  .spot.free     { background: #22c55e20; color: #22c55e; border: 1px solid #22c55e40; }
  .spot.occupied { background: #ef444420; color: #f87171; border: 1px solid #ef444440; }
  .spot .label   { font-size: 0.65rem; font-weight: 400; opacity: 0.7; margin-top: 2px; }
  .form-row { display: flex; gap: 10px; padding: 16px 20px; border-top: 1px solid #2d3748; flex-wrap: wrap; }
  input { background: #0f1117; border: 1px solid #2d3748; border-radius: 8px; color: #e2e8f0; padding: 8px 12px; font-size: 0.875rem; outline: none; }
  input:focus { border-color: #3b82f6; }
  button { background: #3b82f6; color: #fff; border: none; border-radius: 8px; padding: 8px 16px; font-size: 0.875rem; cursor: pointer; font-weight: 500; }
  button:hover { background: #2563eb; }
  button.danger { background: #ef4444; }
  button.danger:hover { background: #dc2626; }
  .refresh-note { font-size: 0.75rem; color: #64748b; }
  .empty { padding: 32px; text-align: center; color: #64748b; font-size: 0.875rem; }
</style>
</head>
<body>
<header>
  <h1>🚗 Smart Garage Admin</h1>
  <span class="badge" id="statusBadge">Connecting...</span>
  <span class="refresh-note" style="margin-left:auto" id="lastRefresh"></span>
</header>
<div class="container">
  <div class="grid-3">
    <div class="card"><h2>Active Sessions</h2><div class="stat" id="statActive">—</div></div>
    <div class="card"><h2>Free Spots</h2><div class="stat" id="statFree">—</div></div>
    <div class="card"><h2>Rate</h2><div class="stat" id="statRate">—<span> EGP/hr</span></div></div>
  </div>
  <div class="section">
    <div class="section-header"><h2>Parking Spots (12)</h2></div>
    <div class="spots-grid" id="spotsGrid">Loading...</div>
  </div>
  <div class="section">
    <div class="section-header"><h2>Active Sessions</h2></div>
    <table>
      <thead><tr><th>Plate</th><th>Customer</th><th>Spot</th><th>Entry</th><th>Duration</th><th>Fee so far</th></tr></thead>
      <tbody id="activeSessions"></tbody>
    </table>
  </div>
  <div class="section">
    <div class="section-header"><h2>Registered Customers</h2></div>
    <table>
      <thead><tr><th>Name</th><th>Plate</th><th>Phone</th><th>PIN</th><th></th></tr></thead>
      <tbody id="customersTable"></tbody>
    </table>
    <div class="form-row">
      <input id="newName"  placeholder="Full name"       style="width:160px"/>
      <input id="newPlate" placeholder="Plate No"        style="width:120px"/>
      <input id="newPhone" placeholder="Phone"           style="width:130px"/>
      <input id="newPin"   placeholder="PIN (4 digits)"  style="width:120px" maxlength="4"/>
      <button onclick="addCustomer()">Add Customer</button>
    </div>
  </div>
  <div class="section">
    <div class="section-header"><h2>Session History</h2></div>
    <table>
      <thead><tr><th>Plate</th><th>Customer</th><th>Spot</th><th>Entry</th><th>Exit</th><th>Duration</th><th>Fee</th></tr></thead>
      <tbody id="historyTable"></tbody>
    </table>
  </div>
</div>
<script>
const SPOTS = ['PL.1','PL.2','PL.3','PL.4','PL.5','PL.6','PL.7','PL.8','PL.9','PL.10','PL.11','PL.12'];

function fmtTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString('en-GB', {hour:'2-digit', minute:'2-digit'});
}
function fmtDur(min) {
  if (min == null) return '—';
  return min < 60 ? min + ' min' : Math.floor(min/60) + 'h ' + (min%60) + 'm';
}

async function refresh() {
  try {
    const d = await (await fetch('/api/admin/data')).json();

    document.getElementById('statusBadge').textContent = 'Live';
    document.getElementById('statusBadge').className   = 'badge';
    document.getElementById('lastRefresh').textContent = 'Last refresh: ' + new Date().toLocaleTimeString();
    document.getElementById('statRate').innerHTML = d.rate + '<span> EGP/hr</span>';

    const active = d.sessions.filter(s => s.status === 'active');
    document.getElementById('statActive').textContent = active.length;

    const occupied = new Set(active.map(s => s.spot_code));
    document.getElementById('statFree').textContent = SPOTS.length - occupied.size;

    document.getElementById('spotsGrid').innerHTML = SPOTS.map(sp => {
      const sess = active.find(s => s.spot_code === sp);
      return `<div class="spot ${sess ? 'occupied' : 'free'}">${sp}<div class="label">${sess ? sess.plate_no : 'Free'}</div></div>`;
    }).join('');

    document.getElementById('activeSessions').innerHTML = active.length
      ? active.map(s => {
          return `<tr><td>${s.plate_no}</td><td>${s.customer_name}</td><td>${s.spot_code}</td><td>${fmtTime(s.entry_time)}</td><td>${fmtDur(s.duration_min)}</td><td>${((s.duration_min/60)*d.rate).toFixed(2)} EGP</td></tr>`;
        }).join('')
      : '<tr><td colspan="6" class="empty">No active sessions</td></tr>';

    document.getElementById('customersTable').innerHTML = d.customers.length
      ? d.customers.map(c => `<tr><td>${c.name}</td><td>${c.plate_no || '—'}</td><td>${c.phone||'—'}</td><td>${c.pin || '—'}</td><td><button class="danger" ${c.plate_no ? '' : 'disabled'} onclick="removeCustomer('${c.plate_no}')">Remove</button></td></tr>`).join('')
      : '<tr><td colspan="5" class="empty">No customers registered</td></tr>';

    const hist = d.sessions.filter(s => s.status === 'completed');
    document.getElementById('historyTable').innerHTML = hist.length
      ? hist.map(s => `<tr><td>${s.plate_no}</td><td>${s.customer_name}</td><td>${s.spot_code}</td><td>${fmtTime(s.entry_time)}</td><td>${fmtTime(s.exit_time)}</td><td>${fmtDur(s.duration_min)}</td><td>${s.fee != null ? s.fee + ' EGP' : '—'}</td></tr>`).join('')
      : '<tr><td colspan="7" class="empty">No completed sessions yet</td></tr>';

  } catch {
    document.getElementById('statusBadge').textContent = 'Offline';
    document.getElementById('statusBadge').className   = 'badge warn';
  }
}

async function addCustomer() {
  const name  = document.getElementById('newName').value.trim();
  const plate = document.getElementById('newPlate').value.trim();
  const phone = document.getElementById('newPhone').value.trim();
  const pin   = document.getElementById('newPin').value.trim() || '1234';
  if (!name || !plate) return alert('Name and plate number are required');
  const res = await fetch('/api/admin/add-customer', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({name, plate_no: plate, phone, pin})
  });
  if (res.ok) {
    ['newName','newPlate','newPhone','newPin'].forEach(id => document.getElementById(id).value = '');
    refresh();
  } else {
    alert((await res.json()).detail);
  }
}

async function removeCustomer(plate) {
  if (!plate || plate === '—') return;
  if (!confirm('Remove ' + plate + '?')) return;
  await fetch('/api/admin/customer/' + plate, {method: 'DELETE'});
  refresh();
}

refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>
"""

@app.get("/admin", response_class=HTMLResponse)
def admin_panel():
    return ADMIN_HTML


@app.on_event("startup")
def startup():
    init_db()
    print(f"\nSmart Garage server running")
    print(f"Admin panel  →  http://localhost:5000/admin")
    print(f"Rate         →  {RATE_PER_HR} EGP/hour\n")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=False)
