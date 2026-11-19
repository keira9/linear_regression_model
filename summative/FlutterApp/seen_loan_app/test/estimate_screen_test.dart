import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:seen_loan_app/main.dart';
import 'package:seen_loan_app/services/loan_api.dart';

Future<void> fillAll(WidgetTester tester) async {
  await tester.enterText(find.byKey(const Key('country')), 'Kenya');
  await tester.enterText(find.byKey(const Key('activity')), 'Retail');
  await tester.enterText(find.byKey(const Key('schedule')), 'monthly');
  await tester.enterText(find.byKey(const Key('term')), '12');
  await tester.enterText(find.byKey(const Key('women')), '1');
  await tester.enterText(find.byKey(const Key('repeat')), 'no');
  FocusManager.instance.primaryFocus?.unfocus();
  await tester.pump();
}

Future<void> tapPredict(WidgetTester tester) async {
  await tester.ensureVisible(find.byKey(const Key('predict')));
  await tester.tap(find.byKey(const Key('predict')));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('the page has six labelled fields and a Predict button',
      (tester) async {
    await tester.pumpWidget(SeenApp(api: LoanApi()));
    expect(find.byType(TextFormField), findsNWidgets(6));
    expect(find.text('Predict'), findsOneWidget);
    expect(find.text('Country'), findsOneWidget);
    expect(find.text('Loan term (months)'), findsOneWidget);
  });

  testWidgets(
      'missing, wrong and out-of-range values are explained in the result panel',
      (tester) async {
    await tester.pumpWidget(SeenApp(api: LoanApi()));
    await tester.enterText(find.byKey(const Key('term')), 'ten');
    await tester.enterText(find.byKey(const Key('women')), '80');
    await tapPredict(tester);
    final message = tester.widget<Text>(find.byKey(const Key('problem'))).data!;
    expect(message, contains('Country is required.'));
    expect(message, contains('Loan term must be a whole number.'));
    expect(message, contains('Women in the group must be between 1 and 50.'));
  });

  testWidgets('a good answer from the API shows the estimate', (tester) async {
    final client = MockClient((request) async => http.Response(
        '{"estimated_loan_usd": 1665.0, "likely_range_usd": [1259.0, 2190.0], "sector": "Retail", '
        '"model": "RandomForest", "model_version": 1}',
        200));
    await tester.pumpWidget(SeenApp(api: LoanApi(client: client)));
    await fillAll(tester);
    await tapPredict(tester);
    expect(find.text('\$1,665'), findsOneWidget);
    expect(find.text('Similar loans usually fall between \$1,259 and \$2,190.'),
        findsOneWidget);
  });

  testWidgets('a validation error from the API is shown as plain text',
      (tester) async {
    final client = MockClient((request) async => http.Response(
        '{"detail": [{"loc": ["body", "country"], "msg": "Value error, \'Kenia\' is not a country the model knows. Closest matches: Kenya."}]}',
        422));
    await tester.pumpWidget(SeenApp(api: LoanApi(client: client)));
    await fillAll(tester);
    await tapPredict(tester);
    expect(
        find.text(
            "country: 'Kenia' is not a country the model knows. Closest matches: Kenya."),
        findsOneWidget);
  });
}
