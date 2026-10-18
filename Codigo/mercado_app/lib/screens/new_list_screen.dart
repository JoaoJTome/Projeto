import 'package:flutter/material.dart';
import '../services/api_service.dart';

class NewListScreen extends StatefulWidget {
  const NewListScreen({super.key});

  @override
  State<NewListScreen> createState() => _NewListScreenState();
}

class _NewListScreenState extends State<NewListScreen> {
  final _searchController = TextEditingController();
  final _titleController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    _titleController.dispose();
    super.dispose();
  }

  final List<String> _currentItems = [];
  List<String> _searchResults = [];
  List<String> _recommended = [];

  bool _searching = false;
  bool _loadingRecommendations = false;
  bool _saving = false;
  String? _error;

  // Número do pedido mais recente de cada tipo. Como a pesquisa é feita a
  // cada tecla e as recomendações a cada alteração da lista, as respostas
  // podem chegar fora de ordem; só a resposta do pedido mais recente é
  // aplicada ao ecrã, as restantes são ignoradas.
  int _searchRequest = 0;
  int _recommendationRequest = 0;

  Future<void> _search(String query) async {
    final pedido = ++_searchRequest;
    if (query.trim().isEmpty) {
      setState(() => _searchResults = []);
      return;
    }
    setState(() => _searching = true);
    try {
      final results = await ApiService.instance.searchItems(query.trim());
      if (!mounted || pedido != _searchRequest) return;
      setState(() => _searchResults = results);
    } catch (e) {
      if (!mounted || pedido != _searchRequest) return;
      setState(() => _error = e.toString());
    } finally {
      if (mounted && pedido == _searchRequest) setState(() => _searching = false);
    }
  }

  Future<void> _addItem(String item) async {
    if (_currentItems.contains(item)) return; // não duplicar
    setState(() {
      _currentItems.add(item);
      _searchResults = [];
      _searchController.clear();
    });
    await _refreshRecommendations();
  }

  Future<void> _refreshRecommendations() async {
    final pedido = ++_recommendationRequest;
    if (_currentItems.isEmpty) {
      setState(() {
        _recommended = [];
        _loadingRecommendations = false;
      });
      return;
    }
    setState(() => _loadingRecommendations = true);
    try {
      final recs = await ApiService.instance.getRecommendations(List.of(_currentItems));
      if (!mounted || pedido != _recommendationRequest) return;
      setState(() {
        // Não recomendar itens que já estão na lista.
        _recommended = recs.where((r) => !_currentItems.contains(r)).toList();
      });
    } catch (e) {
      if (!mounted || pedido != _recommendationRequest) return;
      setState(() => _error = e.toString());
    } finally {
      if (mounted && pedido == _recommendationRequest) {
        setState(() => _loadingRecommendations = false);
      }
    }
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await ApiService.instance.saveList(
        _currentItems,
        title: _titleController.text,
      );
      if (!mounted) return;
      Navigator.of(context).pop();
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Nova lista de compras')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _titleController,
              maxLength: 80,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                labelText: 'Título da lista (opcional)',
                hintText: 'Ex.: Jantar de sábado',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.edit_note),
                counterText: '',
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _searchController,
              decoration: InputDecoration(
                labelText: 'Pesquisar item',
                border: const OutlineInputBorder(),
                suffixIcon: _searching
                    ? const Padding(
                        padding: EdgeInsets.all(12),
                        child: SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      )
                    : const Icon(Icons.search),
              ),
              onChanged: _search,
            ),
            if (_searchResults.isNotEmpty)
              Container(
                constraints: const BoxConstraints(maxHeight: 160),
                margin: const EdgeInsets.only(top: 4),
                decoration: BoxDecoration(border: Border.all(color: Colors.grey.shade300)),
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: _searchResults.length,
                  itemBuilder: (context, index) {
                    final item = _searchResults[index];
                    return ListTile(
                      dense: true,
                      title: Text(item),
                      trailing: const Icon(Icons.add),
                      onTap: () => _addItem(item),
                    );
                  },
                ),
              ),
            const SizedBox(height: 16),
            Text('A minha lista (${_currentItems.length})', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            if (_currentItems.isEmpty)
              const Text('Pesquise e adicione itens acima.', style: TextStyle(color: Colors.grey))
            else
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _currentItems
                    .map((item) => Chip(
                          label: Text(item),
                          onDeleted: () {
                            setState(() => _currentItems.remove(item));
                            _refreshRecommendations();
                          },
                        ))
                    .toList(),
              ),
            const SizedBox(height: 24),
            Row(
              children: [
                Text('Recomendados', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(width: 8),
                if (_loadingRecommendations)
                  const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
              ],
            ),
            const SizedBox(height: 8),
            Expanded(
              child: _currentItems.isEmpty
                  ? const Center(
                      child: Text(
                        'Adicione pelo menos um item para\nver recomendações.',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: Colors.grey),
                      ),
                    )
                  : _recommended.isEmpty && !_loadingRecommendations
                      ? const Center(child: Text('Sem recomendações para já.'))
                      : ListView.builder(
                          itemCount: _recommended.length,
                          itemBuilder: (context, index) {
                            final item = _recommended[index];
                            return ListTile(
                              title: Text(item),
                              trailing: IconButton(
                                icon: const Icon(Icons.add_circle_outline),
                                onPressed: () => _addItem(item),
                              ),
                            );
                          },
                        ),
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(_error!, style: const TextStyle(color: Colors.red)),
              ),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: _currentItems.isEmpty || _saving ? null : _save,
              child: _saving
                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Guardar lista'),
            ),
          ],
        ),
      ),
    );
  }
}
