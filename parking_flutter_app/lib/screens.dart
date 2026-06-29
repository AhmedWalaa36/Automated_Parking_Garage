import 'package:flutter/material.dart';
import 'database/db_helper.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  bool isLoading = false;

  void login() async {
    final email = emailController.text.trim();
    final password = passwordController.text.trim();

    if (email.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please fill all fields')),
      );
      return;
    }

    setState(() => isLoading = true);

    try {
      final user = await DBHelper.login(email, password);

      if (!mounted) return;

      if (user != null) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (context) =>
                HomeScreen(customerId: user['CustomerID'] as int),
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Invalid email or password')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Login error: $e')),
      );
    } finally {
      if (mounted) {
        setState(() => isLoading = false);
      }
    }
  }

  @override
  void dispose() {
    emailController.dispose();
    passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Login'),
        centerTitle: true,
      ),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextField(
              controller: emailController,
              decoration: const InputDecoration(
                labelText: 'Email',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 15),
            TextField(
              controller: passwordController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Password',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: isLoading ? null : login,
              style: ElevatedButton.styleFrom(
                minimumSize: const Size(double.infinity, 50),
              ),
              child: isLoading
                  ? const SizedBox(
                      height: 22,
                      width: 22,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Text('Login'),
            ),
            const SizedBox(height: 10),
            TextButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => const RegisterScreen(),
                  ),
                );
              },
              child: const Text("Don't have an account? Register"),
            ),
          ],
        ),
      ),
    );
  }
}

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final nameController = TextEditingController();
  final phoneController = TextEditingController();
  final emailController = TextEditingController();
  final plateController = TextEditingController();
  final passwordController = TextEditingController();
  bool isLoading = false;

  void register() async {
    final name = nameController.text.trim();
    final phone = phoneController.text.trim();
    final email = emailController.text.trim();
    final plate = plateController.text.trim();
    final password = passwordController.text.trim();

    if (name.isEmpty ||
        phone.isEmpty ||
        email.isEmpty ||
        plate.isEmpty ||
        password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please fill all fields')),
      );
      return;
    }

    if (!email.contains('@')) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Invalid email')),
      );
      return;
    }

    setState(() => isLoading = true);

    try {
      final customerId = await DBHelper.insertCustomer({
        'Name': name,
        'Phone': phone,
        'Email': email,
        'Password': password,
        'Membership': 'standard',
      });

      await DBHelper.insertVehicle({
        'CustomerID': customerId,
        'PlateNo': plate,
      });

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Registered successfully')),
      );

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (context) => const LoginScreen(),
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Register error: $e')),
      );
    } finally {
      if (mounted) {
        setState(() => isLoading = false);
      }
    }
  }

  @override
  void dispose() {
    nameController.dispose();
    phoneController.dispose();
    emailController.dispose();
    plateController.dispose();
    passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Register'),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            TextField(
              controller: nameController,
              decoration: const InputDecoration(
                labelText: 'Name',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 15),
            TextField(
              controller: phoneController,
              decoration: const InputDecoration(
                labelText: 'Phone',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 15),
            TextField(
              controller: emailController,
              decoration: const InputDecoration(
                labelText: 'Email',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 15),
            TextField(
              controller: plateController,
              decoration: const InputDecoration(
                labelText: 'Plate Number',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 15),
            TextField(
              controller: passwordController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Password',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: isLoading ? null : register,
              style: ElevatedButton.styleFrom(
                minimumSize: const Size(double.infinity, 50),
              ),
              child: isLoading
                  ? const SizedBox(
                      height: 22,
                      width: 22,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Text('Register'),
            ),
          ],
        ),
      ),
    );
  }
}

class HomeScreen extends StatefulWidget {
  final int customerId;

  const HomeScreen({super.key, required this.customerId});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<Map<String, dynamic>> vehicles = [];
  Map<int, Map<String, dynamic>?> parkingStatus = {};
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    loadData();
  }

  Future<void> loadData() async {
    setState(() => isLoading = true);

    try {
      vehicles = await DBHelper.getVehiclesByCustomerId(widget.customerId);

      parkingStatus.clear();
      for (final vehicle in vehicles) {
        final vehicleId = vehicle['VehicleID'] as int;
        parkingStatus[vehicleId] =
            await DBHelper.getCurrentParkingStatusByVehicleId(vehicleId);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Load error: $e')),
        );
      }
    }

    if (!mounted) return;
    setState(() => isLoading = false);
  }

  void _showAddVehicleDialog() {
    final plateController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Add Vehicle'),
          content: TextField(
            controller: plateController,
            decoration: const InputDecoration(labelText: 'Plate Number'),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                final plate = plateController.text.trim();
                if (plate.isEmpty) return;

                try {
                  await DBHelper.insertVehicle({
                    'CustomerID': widget.customerId,
                    'PlateNo': plate,
                  });

                  if (!mounted) return;
                  Navigator.pop(context);
                  await loadData();
                } catch (e) {
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Add vehicle error: $e')),
                  );
                }
              },
              child: const Text('Save'),
            ),
          ],
        );
      },
    );
  }

  void _showRetrieveCarDialog() {
    if (vehicles.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No vehicles found.')),
      );
      return;
    }

    int selectedVehicleId = vehicles.first['VehicleID'] as int;

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Retrieve Car'),
          content: DropdownButtonFormField<int>(
            value: selectedVehicleId,
            decoration: const InputDecoration(labelText: 'Vehicle'),
            items: vehicles.map((v) {
              return DropdownMenuItem<int>(
                value: v['VehicleID'] as int,
                child: Text(v['PlateNo'].toString()),
              );
            }).toList(),
            onChanged: (value) {
              if (value != null) {
                selectedVehicleId = value;
              }
            },
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                try {
                  final result = await DBHelper.retrieveCar(selectedVehicleId);

                  if (!mounted) return;
                  Navigator.pop(context);

                  if (result != null) {
                    await loadData();
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => PaymentScreen(session: result),
                      ),
                    );
                  } else {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('This vehicle is not currently parked.'),
                      ),
                    );
                  }
                } catch (e) {
                  if (!mounted) return;
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Retrieve error: $e')),
                  );
                }
              },
              child: const Text('Retrieve'),
            ),
          ],
        );
      },
    );
  }

  Widget _buildVehicleCard(Map<String, dynamic> vehicle) {
    final vehicleId = vehicle['VehicleID'] as int;
    final status = parkingStatus[vehicleId];

    final isParked = status != null;
    final slotText =
        isParked ? 'Parked in: ${status['SpotCode']}' : 'Not Parked';

    return Card(
      child: ListTile(
        leading: const Icon(Icons.directions_car),
        title: Text(vehicle['PlateNo'].toString()),
        subtitle: Text(slotText),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Home'),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: loadData,
          ),
          IconButton(
            icon: const Icon(Icons.person),
            onPressed: () async {
              await Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) =>
                      ProfileScreen(customerId: widget.customerId),
                ),
              );
              await loadData();
            },
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () {
              Navigator.pushReplacement(
                context,
                MaterialPageRoute(
                  builder: (context) => const LoginScreen(),
                ),
              );
            },
          ),
        ],
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: ElevatedButton(
                          onPressed: _showAddVehicleDialog,
                          child: const Text('Add Vehicle'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: ElevatedButton(
                          onPressed: _showRetrieveCarDialog,
                          child: const Text('Retrieve Car'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    'Your Vehicles:',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Expanded(
                    child: vehicles.isEmpty
                        ? const Text('No vehicles found')
                        : RefreshIndicator(
                            onRefresh: loadData,
                            child: ListView.builder(
                              itemCount: vehicles.length,
                              itemBuilder: (context, index) {
                                return _buildVehicleCard(vehicles[index]);
                              },
                            ),
                          ),
                  ),
                ],
              ),
            ),
    );
  }
}

class ProfileScreen extends StatefulWidget {
  final int customerId;

  const ProfileScreen({super.key, required this.customerId});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  Map<String, dynamic>? customer;
  List<Map<String, dynamic>> parkingSessions = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    loadData();
  }

  Future<void> loadData() async {
    setState(() => isLoading = true);

    try {
      customer = await DBHelper.getCustomerById(widget.customerId);
      parkingSessions =
          await DBHelper.getParkingSessionsByCustomerId(widget.customerId);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Profile load error: $e')),
        );
      }
    }

    if (!mounted) return;
    setState(() => isLoading = false);
  }

  void _showEditProfileDialog() {
    if (customer == null) return;

    final nameController = TextEditingController(text: customer!['Name']);
    final phoneController = TextEditingController(text: customer!['Phone']);
    final emailController = TextEditingController(text: customer!['Email']);
    final passwordController =
        TextEditingController(text: customer!['Password']);

    bool obscurePassword = true;

    showDialog(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(24),
              ),
              title: const Text(
                'Edit Profile',
                style: TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF1E3A5F),
                ),
              ),
              content: SingleChildScrollView(
                child: Column(
                  children: [
                    TextField(
                      controller: nameController,
                      decoration: const InputDecoration(
                        labelText: 'Name',
                        prefixIcon: Icon(Icons.person),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: phoneController,
                      decoration: const InputDecoration(
                        labelText: 'Phone',
                        prefixIcon: Icon(Icons.phone),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: emailController,
                      decoration: const InputDecoration(
                        labelText: 'Email',
                        prefixIcon: Icon(Icons.email),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: passwordController,
                      obscureText: obscurePassword,
                      decoration: InputDecoration(
                        labelText: 'Password',
                        prefixIcon: const Icon(Icons.lock),
                        suffixIcon: IconButton(
                          icon: Icon(
                            obscurePassword
                                ? Icons.visibility_off
                                : Icons.visibility,
                          ),
                          onPressed: () {
                            setDialogState(() {
                              obscurePassword = !obscurePassword;
                            });
                          },
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel'),
                ),
                ElevatedButton(
                  onPressed: () async {
                    try {
                      await DBHelper.updateCustomer(widget.customerId, {
                        'Name': nameController.text.trim(),
                        'Phone': phoneController.text.trim(),
                        'Email': emailController.text.trim(),
                        'Password': passwordController.text.trim(),
                      });

                      if (!mounted) return;
                      Navigator.pop(context);
                      await loadData();

                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Profile updated successfully'),
                        ),
                      );
                    } catch (e) {
                      if (!mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('Update error: $e')),
                      );
                    }
                  },
                  child: const Text('Save'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  String _formatDate(String date) {
    return DateTime.parse(date).toLocal().toString();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: loadData,
          ),
          IconButton(
            icon: const Icon(Icons.edit),
            onPressed: _showEditProfileDialog,
          ),
        ],
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : customer == null
              ? const Center(child: Text('Customer not found'))
              : Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(22),
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [
                              Color(0xFF1E3A5F),
                              Color(0xFF2C5D8A),
                            ],
                          ),
                          borderRadius: BorderRadius.circular(22),
                        ),
                        child: Row(
                          children: [
                            CircleAvatar(
                              radius: 34,
                              backgroundColor: Colors.white.withOpacity(0.2),
                              child: const Icon(
                                Icons.person,
                                color: Colors.white,
                                size: 34,
                              ),
                            ),
                            const SizedBox(width: 16),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    customer!['Name'].toString(),
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 24,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    customer!['Email'].toString(),
                                    style: const TextStyle(
                                      color: Colors.white70,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),
                      const Text(
                        'Parking History',
                        style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF1E3A5F),
                        ),
                      ),
                      const SizedBox(height: 10),
                      Expanded(
                        child: parkingSessions.isEmpty
                            ? const Center(child: Text('No sessions'))
                            : RefreshIndicator(
                                onRefresh: loadData,
                                child: ListView.builder(
                                  itemCount: parkingSessions.length,
                                  itemBuilder: (context, index) {
                                    final s = parkingSessions[index];
                                    final isClosed = s['ExitTime'] != null;

                                    return Card(
                                      margin:
                                          const EdgeInsets.only(bottom: 12),
                                      child: ListTile(
                                        leading: Icon(
                                          Icons.local_parking,
                                          color: isClosed
                                              ? Colors.green
                                              : Colors.orange,
                                        ),
                                        title: Text(
                                          '${s['PlateNo']} - ${s['SpotCode']}',
                                        ),
                                        subtitle: Text(
                                          'Entry: ${_formatDate(s['EntryTime'].toString())}\n'
                                          'Exit: ${s['ExitTime'] == null ? "Still parked" : _formatDate(s['ExitTime'].toString())}\n'
                                          'Fee: ${s['Fee'] ?? 0} EGP',
                                        ),
                                        isThreeLine: true,
                                      ),
                                    );
                                  },
                                ),
                              ),
                      ),
                    ],
                  ),
                ),
    );
  }
}

class PaymentScreen extends StatelessWidget {
  final Map<String, dynamic> session;

  const PaymentScreen({super.key, required this.session});

  @override
  Widget build(BuildContext context) {
    final entry = session['EntryTime'] is DateTime
        ? session['EntryTime'] as DateTime
        : DateTime.parse(session['EntryTime'].toString());

    final exit = session['ExitTime'] is DateTime
        ? session['ExitTime'] as DateTime
        : DateTime.parse(session['ExitTime'].toString());

    final duration = exit.difference(entry);
    final hours = (duration.inMinutes / 60).ceil();
    final fee = (session['Fee'] as num).toDouble();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Payments'),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Card(
            elevation: 6,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(24),
            ),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CircleAvatar(
                    radius: 34,
                    backgroundColor: Colors.green.shade100,
                    child: Icon(
                      Icons.receipt_long,
                      size: 34,
                      color: Colors.green.shade700,
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Payment Receipt',
                    style: TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF1E3A5F),
                    ),
                  ),
                  const SizedBox(height: 24),
                  _paymentRow('Vehicle', session['PlateNo'].toString()),
                  _paymentRow('Slot', session['SpotCode'].toString()),
                  _paymentRow('Entry Time', entry.toLocal().toString()),
                  _paymentRow('Exit Time', exit.toLocal().toString()),
                  _paymentRow('Duration', '$hours hour(s)'),
                  const Divider(height: 30),
                  _paymentRow(
                    'Total',
                    '${fee.toStringAsFixed(2)} EGP',
                    isBold: true,
                  ),
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: () {
                        Navigator.popUntil(context, (route) => route.isFirst);
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.green,
                      ),
                      child: const Text('Done'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _paymentRow(String title, String value, {bool isBold = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: TextStyle(
                fontSize: 16,
                fontWeight: isBold ? FontWeight.bold : FontWeight.w500,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              textAlign: TextAlign.end,
              style: TextStyle(
                fontSize: 16,
                fontWeight: isBold ? FontWeight.bold : FontWeight.w400,
                color: isBold ? const Color(0xFF1E3A5F) : Colors.black87,
              ),
            ),
          ),
        ],
      ),
    );
  }
}