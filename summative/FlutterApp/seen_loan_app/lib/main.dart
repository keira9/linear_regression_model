import 'package:flutter/material.dart';

import 'screens/estimate_screen.dart';
import 'services/loan_api.dart';

void main() => runApp(SeenApp(api: LoanApi()));

class SeenApp extends StatelessWidget {
  const SeenApp({super.key, required this.api});

  final LoanApi api;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Seen',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6A1B9A)),
        inputDecorationTheme: const InputDecorationTheme(
          filled: true,
          border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(10))),
        ),
      ),
      home: EstimateScreen(api: api),
    );
  }
}
