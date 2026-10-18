import 'package:flutter/material.dart';
import 'services/api_service.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(const MercadoApp());
}

class MercadoApp extends StatelessWidget {
  const MercadoApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Análise de Cesto de Compras',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: Colors.green,
        useMaterial3: true,
      ),
      home: const _StartupGate(),
    );
  }
}

/// Verifica se já existe um token de sessão guardado (SharedPreferences)
/// e decide se arranca no Login ou diretamente no Início.
class _StartupGate extends StatefulWidget {
  const _StartupGate();

  @override
  State<_StartupGate> createState() => _StartupGateState();
}

class _StartupGateState extends State<_StartupGate> {
  bool? _hasSession;

  @override
  void initState() {
    super.initState();
    ApiService.instance.hasSession().then((value) {
      if (mounted) setState(() => _hasSession = value);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_hasSession == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return _hasSession! ? const HomeScreen() : const LoginScreen();
  }
}
