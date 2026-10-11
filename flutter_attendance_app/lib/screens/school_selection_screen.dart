import 'package:flutter/material.dart';

import '../models/school.dart';
import '../services/school_directory_service.dart';
import '../services/school_preference_store.dart';

class SchoolSelectionScreen extends StatefulWidget {
  const SchoolSelectionScreen({
    required this.onSchoolSelected,
    required this.directory,
    required this.preferenceStore,
    super.key,
  });

  final ValueChanged<School> onSchoolSelected;
  final SchoolDirectory directory;
  final SchoolPreferenceStore preferenceStore;

  @override
  State<SchoolSelectionScreen> createState() => _SchoolSelectionScreenState();
}

class _SchoolSelectionScreenState extends State<SchoolSelectionScreen> {
  final _searchController = TextEditingController();
  List<School> _schools = const [];
  School? _selectedSchool;
  String _query = '';
  String? _error;
  bool _isLoading = true;
  bool _isContinuing = false;

  List<School> get _filteredSchools {
    final query = _query.trim().toLowerCase();
    if (query.isEmpty) return _schools;
    return _schools
        .where(
          (school) =>
              school.name.toLowerCase().contains(query) ||
              school.slug.toLowerCase().contains(query),
        )
        .toList(growable: false);
  }

  @override
  void initState() {
    super.initState();
    _loadSchools();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadSchools() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final results = await widget.directory.fetchSchools();
      final savedSlug = await widget.preferenceStore.readLastSchoolSlug();
      if (!mounted) return;
      School? previous;
      for (final school in results) {
        if (school.slug == savedSlug) {
          previous = school;
          break;
        }
      }
      setState(() {
        _schools = results;
        _selectedSchool = previous;
        _isLoading = false;
      });
    } on SchoolDirectoryException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'The school list could not be loaded. Try again.';
        _isLoading = false;
      });
    }
  }

  Future<void> _continue() async {
    final school = _selectedSchool;
    if (school == null || _isContinuing) return;
    setState(() => _isContinuing = true);
    await widget.preferenceStore.saveLastSchoolSlug(school.slug);
    if (!mounted) return;
    widget.onSchoolSelected(school);
    setState(() => _isContinuing = false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Container(
              width: double.infinity,
              color: theme.colorScheme.surfaceContainerLow,
              padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 560),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: theme.colorScheme.primary,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(
                          Icons.school_outlined,
                          color: theme.colorScheme.onPrimary,
                          semanticLabel: 'PastMaster SMS',
                        ),
                      ),
                      const SizedBox(height: 20),
                      Text(
                        'Choose your school',
                        style: theme.textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Attendance will open on your school’s secure portal.',
                        style: theme.textTheme.bodyLarge?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            Expanded(
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 560),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        TextField(
                          controller: _searchController,
                          enabled: !_isLoading && _error == null,
                          onChanged: (value) => setState(() => _query = value),
                          decoration: InputDecoration(
                            labelText: 'Search schools',
                            hintText: 'School name',
                            prefixIcon: const Icon(Icons.search),
                            suffixIcon: _query.isEmpty
                                ? null
                                : IconButton(
                                    tooltip: 'Clear search',
                                    onPressed: () {
                                      _searchController.clear();
                                      setState(() => _query = '');
                                    },
                                    icon: const Icon(Icons.close),
                                  ),
                          ),
                        ),
                        const SizedBox(height: 20),
                        Expanded(child: _buildSchoolList(context)),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            DecoratedBox(
              decoration: BoxDecoration(
                color: theme.colorScheme.surface,
                border: Border(
                  top: BorderSide(color: theme.colorScheme.outlineVariant),
                ),
              ),
              child: SafeArea(
                top: false,
                minimum: const EdgeInsets.fromLTRB(20, 12, 20, 16),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 560),
                    child: SizedBox(
                      width: double.infinity,
                      height: 48,
                      child: FilledButton(
                        key: const Key('continue_button'),
                        onPressed: _selectedSchool == null || _isContinuing
                            ? null
                            : _continue,
                        child: _isContinuing
                            ? const SizedBox.square(
                                dimension: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Text('Next'),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSchoolList(BuildContext context) {
    if (_isLoading) return const _SchoolListSkeleton();
    if (_error != null) {
      return _MessageState(
        icon: Icons.cloud_off_outlined,
        title: 'Could not load schools',
        message: _error!,
        actionLabel: 'Try again',
        onAction: _loadSchools,
      );
    }
    if (_schools.isEmpty) {
      return const _MessageState(
        icon: Icons.domain_disabled_outlined,
        title: 'No schools are available',
        message: 'Ask your administrator to add an active school domain.',
      );
    }
    final schools = _filteredSchools;
    if (schools.isEmpty) {
      return _MessageState(
        icon: Icons.search_off_outlined,
        title: 'No matching school',
        message: 'Check the spelling or clear your search.',
        actionLabel: 'Clear search',
        onAction: () {
          _searchController.clear();
          setState(() => _query = '');
        },
      );
    }

    return ListView.separated(
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      itemCount: schools.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final school = schools[index];
        final selected = school.slug == _selectedSchool?.slug;
        return Semantics(
          selected: selected,
          button: true,
          label: '${school.name}${selected ? ', selected' : ''}',
          child: Material(
            color: selected
                ? Theme.of(context).colorScheme.primaryContainer
                : Theme.of(context).colorScheme.surface,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(
                color: selected
                    ? Theme.of(context).colorScheme.primary
                    : Theme.of(context).colorScheme.outlineVariant,
              ),
            ),
            child: InkWell(
              key: Key('school_${school.slug}'),
              borderRadius: BorderRadius.circular(12),
              onTap: () => setState(() => _selectedSchool = school),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 14,
                ),
                child: Row(
                  children: [
                    Icon(
                      selected
                          ? Icons.check_circle
                          : Icons.circle_outlined,
                      color: selected
                          ? Theme.of(context).colorScheme.primary
                          : Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        school.name,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _SchoolListSkeleton extends StatelessWidget {
  const _SchoolListSkeleton();

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.surfaceContainerHighest;
    return Semantics(
      label: 'Loading schools',
      child: ListView.separated(
        itemCount: 4,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (_, index) => Container(
          height: 58,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }
}

class _MessageState extends StatelessWidget {
  const _MessageState({
    required this.icon,
    required this.title,
    required this.message,
    this.actionLabel,
    this.onAction,
  });

  final IconData icon;
  final String title;
  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 40,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(
              message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 16),
              OutlinedButton(onPressed: onAction, child: Text(actionLabel!)),
            ],
          ],
        ),
      ),
    );
  }
}
