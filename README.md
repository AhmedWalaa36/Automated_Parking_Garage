# 🚗 Automated Parking Garage System

## 📌 Overview

The **Automated Parking Garage System** is a graduation project that automates the parking process using computer vision, embedded systems, and a mobile application.

The system recognizes vehicle license plates using an ESP32-CAM and OCR, assigns an available parking space automatically, and allows users to retrieve their vehicles through a Flutter mobile application.

---

## 👥 Team Members

* Ahmed Walaa
* Ahmed Osama El-Sayed
* Menatallah Nasser Hussein
* Mohamed Khaled Soliman
* Youssef Mahmoud Moataz

---

## 🛠 Technologies Used

### Backend

* Python
* FastAPI
* SQLite
* OpenCV
* Tesseract OCR
* Pillow

### Mobile Application

* Flutter
* Dart
* HTTP REST API

### Embedded Systems

* ESP32
* ESP32-CAM
* Arduino IDE
* Stepper Motors
* Ultrasonic Sensors
* IR Sensors

---

## 📂 Project Structure

```
Automated_Parking_Garage/
│
├── Backend/                # FastAPI Server
├── Database/               # SQLite Database
├── esp32/                  # ESP32 Controller Code
├── EspCam/                 # ESP32-CAM Code
└── parking_flutter_app/    # Flutter Mobile Application
```

---

## ✨ Features

* Vehicle License Plate Recognition (OCR)
* Automatic Parking Space Allocation
* Smart Vehicle Retrieval
* Live Parking Status
* Customer Registration & Login
* Vehicle Management
* Parking Session Tracking
* Admin Dashboard
* REST API Communication
* ESP32 Hardware Integration

---

## 🔄 System Workflow

1. User registers through the Flutter application.
2. Vehicle information is stored in the database.
3. ESP32-CAM captures the vehicle plate.
4. Backend recognizes the plate using OCR.
5. The server verifies the customer.
6. An available parking spot is assigned.
7. ESP32 moves the vehicle to the assigned parking location.
8. Parking session is stored in the database.
9. User requests vehicle retrieval through the app.
10. ESP32 returns the vehicle automatically.

---

## 🗄 Database

The system uses a relational SQLite database consisting of:

* Customers
* Vehicles
* ParkingSpots
* ParkingSessions
* Payments
* Logs

---

## 🚀 Getting Started

### Backend

```bash
cd Backend
pip install -r requirements.txt
python main.py
```

### Flutter

```bash
cd parking_flutter_app
flutter pub get
flutter run
```

---

## 📡 API

The backend provides REST APIs for:

* Authentication
* Customer Management
* Vehicle Management
* Parking Sessions
* Vehicle Retrieval
* ESP32 Communication
* Admin Dashboard

---

## 📱 Hardware Components

* ESP32
* ESP32-CAM
* Stepper Motors
* IR Sensors
* Ultrasonic Sensors
* Conveyor System

---

## 🎓 Graduation Project

Faculty of Computers and Artificial Intelligence

Ain Shams University

2026

---

## 📄 License

This project was developed for educational purposes as a Graduation Project.
