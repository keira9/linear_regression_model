import 'package:flutter/material.dart';

import '../data/choices.dart';
import '../services/loan_api.dart';

/// The single page of the app: six inputs, a Predict button and a result panel.
class EstimateScreen extends StatefulWidget {
  const EstimateScreen({super.key, required this.api});

  final LoanApi api;

  @override
  State<EstimateScreen> createState() => _EstimateScreenState();
}

class _EstimateScreenState extends State<EstimateScreen> {
  final _formKey = GlobalKey<FormState>();
  final _term = TextEditingController();
  final _women = TextEditingController(text: '1');
  final _repeat = TextEditingController(text: 'no');
  TextEditingController? _country;
  TextEditingController? _activity;
  TextEditingController? _schedule;

  bool _busy = false;
  LoanEstimate? _estimate;
  String? _problem;

  @override
  void dispose() {
    _term.dispose();
    _women.dispose();
    _repeat.dispose();
    super.dispose();
  }

  // ---------- checks shared by the field validators and the result panel ----------

  static String? _needText(String? value, String name) =>
      (value == null || value.trim().isEmpty) ? '$name is required.' : null;

  static String? _needWholeNumber(
      String? value, String name, int min, int max) {
    if (value == null || value.trim().isEmpty) return '$name is required.';
    final number = int.tryParse(value.trim());
    if (number == null) return '$name must be a whole number.';
    if (number < min || number > max) {
      return '$name must be between $min and $max.';
    }
    return null;
  }

  static String? _needYesNo(String? value) {
    final answer = (value ?? '').trim().toLowerCase();
    if (answer.isEmpty) return 'Repeat borrower is required.';
    if (answer != 'yes' && answer != 'no') {
      return 'Repeat borrower must be yes or no.';
    }
    return null;
  }

  static String? _needSchedule(String? value) {
    final missing = _needText(value, 'Repayment schedule');
    if (missing != null) return missing;
    if (!repaymentSchedules.contains(value!.trim().toLowerCase())) {
      return 'Repayment schedule must be one of: ${repaymentSchedules.join(', ')}.';
    }
    return null;
  }

  List<String> _allProblems() {
    return [
      _needText(_country?.text, 'Country'),
      _needText(_activity?.text, 'Business activity'),
      _needSchedule(_schedule?.text),
      _needWholeNumber(_term.text, 'Loan term', 1, 60),
      _needWholeNumber(_women.text, 'Women in the group', 1, 50),
      _needYesNo(_repeat.text),
    ].whereType<String>().toList();
  }

  // ---------- actions ----------

  Future<void> _predict() async {
    FocusScope.of(context).unfocus();
    _formKey.currentState!.validate();
    final problems = _allProblems();
    if (problems.isNotEmpty) {
      setState(() {
        _estimate = null;
        _problem = problems.join('\n');
      });
      return;
    }

    setState(() {
      _busy = true;
      _estimate = null;
      _problem = null;
    });
    try {
      final result = await widget.api.estimate(
        country: _country!.text.trim(),
        activity: _activity!.text.trim(),
        repaymentInterval: _schedule!.text.trim().toLowerCase(),
        termInMonths: int.parse(_term.text.trim()),
        borrowerCount: int.parse(_women.text.trim()),
        repeatBorrower: _repeat.text.trim().toLowerCase() == 'yes',
      );
      if (mounted) setState(() => _estimate = result);
    } on LoanApiError catch (error) {
      if (mounted) setState(() => _problem = error.message);
    } catch (error) {
      if (mounted) setState(() => _problem = 'Unexpected problem: $error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  // ---------- layout ----------

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _Header(colors: colors),
              const SizedBox(height: 20),
              Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const _SectionTitle('Her business'),
                    _suggestionField(
                      fieldKey: const Key('country'),
                      label: 'Country',
                      hint: 'e.g. Kenya',
                      options: countries,
                      keep: (c) => _country = c,
                      validator: (v) => _needText(v, 'Country'),
                    ),
                    const SizedBox(height: 12),
                    _suggestionField(
                      fieldKey: const Key('activity'),
                      label: 'Business activity',
                      hint: 'e.g. Retail, Farming, Tailoring',
                      options: activities,
                      keep: (c) => _activity = c,
                      validator: (v) => _needText(v, 'Business activity'),
                    ),
                    const SizedBox(height: 20),
                    const _SectionTitle('The loan'),
                    _suggestionField(
                      fieldKey: const Key('schedule'),
                      label: 'Repayment schedule',
                      hint: 'monthly, irregular, bullet or weekly',
                      options: repaymentSchedules,
                      keep: (c) => _schedule = c,
                      validator: _needSchedule,
                    ),
                    const SizedBox(height: 12),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: TextFormField(
                            key: const Key('term'),
                            controller: _term,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                                labelText: 'Loan term (months)',
                                hintText: '1 to 60'),
                            validator: (v) =>
                                _needWholeNumber(v, 'Loan term', 1, 60),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            key: const Key('women'),
                            controller: _women,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                                labelText: 'Women in the group',
                                hintText: '1 to 50'),
                            validator: (v) => _needWholeNumber(
                                v, 'Women in the group', 1, 50),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      key: const Key('repeat'),
                      controller: _repeat,
                      decoration: const InputDecoration(
                        labelText: 'Repeat borrower (yes or no)',
                        hintText: 'Has she borrowed on Kiva before?',
                      ),
                      validator: _needYesNo,
                    ),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      key: const Key('predict'),
                      onPressed: _busy ? null : _predict,
                      icon: _busy
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.calculate_outlined),
                      label: const Text('Predict'),
                      style: FilledButton.styleFrom(
                          minimumSize: const Size.fromHeight(52)),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              _ResultPanel(busy: _busy, estimate: _estimate, problem: _problem),
            ],
          ),
        ),
      ),
    );
  }

  Widget _suggestionField({
    required Key fieldKey,
    required String label,
    required String hint,
    required List<String> options,
    required void Function(TextEditingController) keep,
    required String? Function(String?) validator,
  }) {
    return Autocomplete<String>(
      optionsBuilder: (TextEditingValue typed) {
        final text = typed.text.trim().toLowerCase();
        if (text.isEmpty) return const Iterable<String>.empty();
        return options
            .where((option) => option.toLowerCase().contains(text))
            .take(8);
      },
      fieldViewBuilder: (context, controller, focusNode, onFieldSubmitted) {
        keep(controller);
        return TextFormField(
          key: fieldKey,
          controller: controller,
          focusNode: focusNode,
          textInputAction: TextInputAction.next,
          decoration: InputDecoration(labelText: label, hintText: hint),
          validator: validator,
        );
      },
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.colors});

  final ColorScheme colors;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
          color: colors.primaryContainer,
          borderRadius: BorderRadius.circular(16)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Seen',
              style: text.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                  color: colors.onPrimaryContainer)),
          const SizedBox(height: 4),
          Text('Not unbankable, just unseen.',
              style:
                  text.titleSmall?.copyWith(color: colors.onPrimaryContainer)),
          const SizedBox(height: 8),
          Text(
            'Estimate the loan a woman-led business in Africa is likely to raise, based on 100,000 past Kiva loans.',
            style: text.bodyMedium?.copyWith(color: colors.onPrimaryContainer),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Text(title,
          style: Theme.of(context)
              .textTheme
              .titleMedium
              ?.copyWith(fontWeight: FontWeight.w600)),
    );
  }
}

class _ResultPanel extends StatelessWidget {
  const _ResultPanel(
      {required this.busy, required this.estimate, required this.problem});

  final bool busy;
  final LoanEstimate? estimate;
  final String? problem;

  static String _usd(double value) {
    final digits = value.round().toString();
    final out = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i > 0 && (digits.length - i) % 3 == 0) out.write(',');
      out.write(digits[i]);
    }
    return '\$$out';
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;

    late final Color background;
    late final Widget child;
    if (busy) {
      background = colors.surfaceContainerHigh;
      child = const Text(
          'Asking the model... the first request after a quiet period can take up to a minute.');
    } else if (problem != null) {
      background = colors.errorContainer;
      child = Text(problem!,
          key: const Key('problem'),
          style: TextStyle(color: colors.onErrorContainer));
    } else if (estimate != null) {
      final e = estimate!;
      background = colors.secondaryContainer;
      child = Column(
        key: const Key('estimate'),
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Estimated loan size', style: text.labelLarge),
          const SizedBox(height: 4),
          Text(_usd(e.amountUsd),
              style: text.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          Text(
              'Similar loans usually fall between ${_usd(e.lowUsd)} and ${_usd(e.highUsd)}.'),
          const SizedBox(height: 4),
          Text('Sector: ${e.sector}', style: text.bodySmall),
        ],
      );
    } else {
      background = colors.surfaceContainerHigh;
      child = const Text(
          'Fill in the six fields and tap Predict. The estimate will appear here.');
    }

    return Container(
      key: const Key('result'),
      constraints: const BoxConstraints(minHeight: 96),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
          color: background, borderRadius: BorderRadius.circular(16)),
      child: child,
    );
  }
}
