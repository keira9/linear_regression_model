import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

/// Address of the deployed API. Change this line if your Render service has a different name.
const String apiBaseUrl = 'https://seen-loan-api.onrender.com';

class LoanEstimate {
  const LoanEstimate({
    required this.amountUsd,
    required this.lowUsd,
    required this.highUsd,
    required this.sector,
  });

  final double amountUsd;
  final double lowUsd;
  final double highUsd;
  final String sector;

  static LoanEstimate fromJson(Map<String, dynamic> json) {
    final range = (json['likely_range_usd'] as List<dynamic>).cast<num>();
    return LoanEstimate(
      amountUsd: (json['estimated_loan_usd'] as num).toDouble(),
      lowUsd: range[0].toDouble(),
      highUsd: range[1].toDouble(),
      sector: json['sector'] as String,
    );
  }
}

/// A problem that can be shown to the user as it is.
class LoanApiError implements Exception {
  const LoanApiError(this.message);
  final String message;

  @override
  String toString() => message;
}

class LoanApi {
  LoanApi({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<LoanEstimate> estimate({
    required String country,
    required String activity,
    required String repaymentInterval,
    required int termInMonths,
    required int borrowerCount,
    required bool repeatBorrower,
  }) async {
    http.Response response;
    try {
      response = await _client
          .post(
            Uri.parse('$apiBaseUrl/predict'),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode({
              'country': country,
              'activity': activity,
              'repayment_interval': repaymentInterval,
              'term_in_months': termInMonths,
              'borrower_count': borrowerCount,
              'repeat_borrower': repeatBorrower,
            }),
          )
          .timeout(const Duration(seconds: 90));
    } on TimeoutException {
      throw const LoanApiError(
          'The server took too long to answer. It may be waking up, try again in a moment.');
    } on http.ClientException {
      throw const LoanApiError(
          'No connection to the server. Check the internet connection and try again.');
    }

    Object? decoded;
    try {
      decoded = jsonDecode(response.body);
    } on FormatException {
      decoded = null;
    }
    if (response.statusCode == 200 && decoded is Map<String, dynamic>) {
      return LoanEstimate.fromJson(decoded);
    }
    if (response.statusCode == 422 &&
        decoded is Map &&
        decoded['detail'] is List) {
      final problems = (decoded['detail'] as List).map((item) {
        final field =
            ((item['loc'] as List).last).toString().replaceAll('_', ' ');
        final text = item['msg'].toString().replaceFirst('Value error, ', '');
        return '$field: $text';
      });
      throw LoanApiError(problems.join('\n'));
    }
    throw LoanApiError(
        'The server returned an error (code ${response.statusCode}).');
  }
}
