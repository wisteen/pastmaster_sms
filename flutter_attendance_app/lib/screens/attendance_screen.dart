import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';

import '../models/school.dart';

class AttendanceScreen extends StatefulWidget {
  const AttendanceScreen({required this.school, super.key});

  final School school;

  @override
  State<AttendanceScreen> createState() => _AttendanceScreenState();
}

class _AttendanceScreenState extends State<AttendanceScreen> {
  late final WebViewController _controller;
  bool _isLoading = true;
  bool _cameraDenied = false;
  String? _pageError;
  String _pageLabel = 'Sign in';

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFFF9FAFC))
      ..setNavigationDelegate(
        NavigationDelegate(
          onNavigationRequest: _handleNavigation,
          onPageStarted: (url) {
            if (!mounted) return;
            setState(() {
              _isLoading = true;
              _pageError = null;
              _pageLabel = _labelForUrl(url);
            });
          },
          onPageFinished: (url) {
            if (!mounted) return;
            setState(() {
              _isLoading = false;
              _pageLabel = _labelForUrl(url);
            });
          },
          onWebResourceError: (error) {
            if (error.isForMainFrame != true || !mounted) return;
            setState(() {
              _isLoading = false;
              _pageError = 'This school portal could not be opened.';
            });
          },
        ),
      );
    unawaited(_preparePortal());
  }

  Future<void> _preparePortal() async {
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      final status = await Permission.camera.request();
      if (mounted) setState(() => _cameraDenied = !status.isGranted);

      final platformController = _controller.platform;
      if (platformController is AndroidWebViewController) {
        await platformController.setOnPlatformPermissionRequest((request) {
          unawaited(_answerWebPermissionRequest(request));
        });
      }
    }
    await _controller.loadRequest(widget.school.loginUrl);
  }

  Future<void> _answerWebPermissionRequest(
    PlatformWebViewPermissionRequest request,
  ) async {
    final cameraOnly = request.types.isNotEmpty &&
        request.types.every(
          (type) => type == WebViewPermissionResourceType.camera,
        );
    final cameraGranted = await Permission.camera.isGranted;
    if (cameraOnly && cameraGranted) {
      await request.grant();
    } else {
      await request.deny();
    }
  }

  NavigationDecision _handleNavigation(NavigationRequest request) {
    final target = Uri.tryParse(request.url);
    final selected = widget.school.baseUrl;
    if (target != null &&
        (target.scheme == 'https' || target.scheme == 'http') &&
        target.host.toLowerCase() == selected.host.toLowerCase()) {
      return NavigationDecision.navigate;
    }
    return NavigationDecision.prevent;
  }

  String _labelForUrl(String value) {
    final uri = Uri.tryParse(value);
    return uri?.path.startsWith('/attendance/mark/') == true
        ? 'Clock in'
        : 'Sign in';
  }

  Future<void> _handleBack() async {
    if (await _controller.canGoBack()) {
      await _controller.goBack();
      return;
    }
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _changeSchool() async {
    await WebViewCookieManager().clearCookies();
    if (mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) unawaited(_handleBack());
      },
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            tooltip: 'Back',
            onPressed: _handleBack,
            icon: const Icon(Icons.arrow_back),
          ),
          titleSpacing: 4,
          title: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.school.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text(
                _pageLabel,
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
            ],
          ),
          actions: [
            IconButton(
              tooltip: 'Refresh',
              onPressed: _controller.reload,
              icon: const Icon(Icons.refresh),
            ),
            PopupMenuButton<String>(
              tooltip: 'More options',
              onSelected: (value) {
                if (value == 'clock-in') {
                  _controller.loadRequest(widget.school.clockInUrl);
                } else if (value == 'change-school') {
                  unawaited(_changeSchool());
                }
              },
              itemBuilder: (_) => const [
                PopupMenuItem(
                  value: 'clock-in',
                  child: Text('Open clock in'),
                ),
                PopupMenuItem(
                  value: 'change-school',
                  child: Text('Change school'),
                ),
              ],
            ),
          ],
        ),
        body: Column(
          children: [
            if (_cameraDenied)
              MaterialBanner(
                content: const Text(
                  'Camera access is off. Enable it to scan ID cards.',
                ),
                leading: const Icon(Icons.no_photography_outlined),
                actions: [
                  TextButton(
                    onPressed: openAppSettings,
                    child: const Text('Open settings'),
                  ),
                ],
              ),
            Expanded(
              child: Stack(
                children: [
                  WebViewWidget(controller: _controller),
                  if (_isLoading)
                    const LinearProgressIndicator(minHeight: 3),
                  if (_pageError != null)
                    ColoredBox(
                      color: Theme.of(context).colorScheme.surface,
                      child: Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.cloud_off_outlined, size: 44),
                              const SizedBox(height: 12),
                              Text(
                                _pageError!,
                                textAlign: TextAlign.center,
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              const SizedBox(height: 16),
                              FilledButton.tonal(
                                onPressed: () => _controller.loadRequest(
                                  widget.school.loginUrl,
                                ),
                                child: const Text('Try again'),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
