import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import '../../theme/app_colors.dart';

class _PasswordRule {
  final bool Function(String) test;
  final String label;
  const _PasswordRule(this.test, this.label);
}

final _passwordRules = <_PasswordRule>[
  _PasswordRule((pw) => pw.length >= 8, 'At least 8 characters'),
  _PasswordRule((pw) => RegExp(r'[A-Z]').hasMatch(pw), 'An uppercase letter'),
  _PasswordRule((pw) => RegExp(r'[a-z]').hasMatch(pw), 'A lowercase letter'),
  _PasswordRule((pw) => RegExp(r'\d').hasMatch(pw), 'A number'),
  _PasswordRule((pw) => RegExp(r'[^A-Za-z0-9]').hasMatch(pw), 'A symbol'),
];

class SignupScreen extends StatefulWidget {
  final String redirect;
  const SignupScreen({super.key, this.redirect = '/'});

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  final _nameCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();
  String? _error;
  bool _submitting = false;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  bool get _passwordsMatch => _confirmCtrl.text.isEmpty || _passwordCtrl.text == _confirmCtrl.text;

  Future<void> _submit() async {
    setState(() => _error = null);
    final failedRules = _passwordRules.where((r) => !r.test(_passwordCtrl.text)).toList();
    if (failedRules.isNotEmpty) {
      setState(() => _error = 'Password does not meet all the requirements below.');
      return;
    }
    if (_passwordCtrl.text != _confirmCtrl.text) {
      setState(() => _error = "Passwords don't match.");
      return;
    }
    setState(() => _submitting = true);
    try {
      await context.read<AuthProvider>().signup(
            email: _emailCtrl.text.trim(),
            password: _passwordCtrl.text,
            name: _nameCtrl.text.trim(),
          );
      if (mounted) context.go(widget.redirect);
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Create your account')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(controller: _nameCtrl, decoration: const InputDecoration(labelText: 'Name')),
            const SizedBox(height: 12),
            TextField(
              controller: _emailCtrl,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(labelText: 'Email', helperText: 'Use a valid email address.'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _passwordCtrl,
              obscureText: true,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(labelText: 'Password'),
            ),
            const SizedBox(height: 6),
            ..._passwordRules.map((r) {
              final met = r.test(_passwordCtrl.text);
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 1),
                child: Text(
                  '${met ? '✓' : '·'} ${r.label}',
                  style: TextStyle(fontSize: 12, color: met ? AppColors.primary : AppColors.inkMuted),
                ),
              );
            }),
            const SizedBox(height: 8),
            TextField(
              controller: _confirmCtrl,
              obscureText: true,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(labelText: 'Confirm password'),
            ),
            if (!_passwordsMatch)
              const Padding(
                padding: EdgeInsets.only(top: 4),
                child: Text("Passwords don't match.", style: TextStyle(fontSize: 12, color: AppColors.warning)),
              ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: AppColors.warning)),
            ],
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _submitting ? null : _submit,
              child: Text(_submitting ? 'Creating account…' : 'Create account'),
            ),
            const SizedBox(height: 16),
            Center(
              child: TextButton(
                onPressed: () => context.go('/login?redirect=${Uri.encodeComponent(widget.redirect)}'),
                child: const Text('Already have an account? Sign in'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
