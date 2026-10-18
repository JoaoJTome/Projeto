import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';
import 'login_screen.dart';
import 'new_list_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late Future<List<SavedList>> _listsFuture;

  /// Itens marcados (checkbox) por lista: id da lista -> nomes dos itens.
  /// Guardado localmente no dispositivo com SharedPreferences, para que as
  /// marcações se mantenham depois de fechar a app.
  final Map<String, Set<String>> _checked = {};
  SharedPreferences? _prefs;

  @override
  void initState() {
    super.initState();
    _listsFuture = _loadLists();
  }

  Future<List<SavedList>> _loadLists() async {
    _prefs ??= await SharedPreferences.getInstance();
    final lists = await ApiService.instance.getLists();
    _checked.clear();
    for (final list in lists) {
      _checked[list.id] =
          (_prefs!.getStringList(_checkedKey(list.id)) ?? []).toSet();
    }
    return lists;
  }

  String _checkedKey(String listId) => 'checked_items_$listId';

  Future<void> _toggleItem(String listId, String item, bool value) async {
    final set = _checked.putIfAbsent(listId, () => <String>{});
    setState(() {
      value ? set.add(item) : set.remove(item);
    });
    await _prefs?.setStringList(_checkedKey(listId), set.toList());
  }

  /// Abre um diálogo para mudar o título de uma lista e grava-o na API.
  Future<void> _renameList(SavedList list) async {
    final controller = TextEditingController(text: list.title ?? '');
    final newTitle = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Título da lista'),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLength: 80,
          textCapitalization: TextCapitalization.sentences,
          decoration: const InputDecoration(
            hintText: 'Ex.: Jantar de sábado',
            helperText: 'Deixe vazio para remover o título.',
          ),
          onSubmitted: (v) => Navigator.of(ctx).pop(v),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(controller.text),
            child: const Text('Guardar'),
          ),
        ],
      ),
    );
    if (newTitle == null) return; // cancelado

    try {
      await ApiService.instance.renameList(list.id, newTitle);
      await _refresh();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Não foi possível mudar o título: $e')),
      );
    }
  }

  Future<void> _refresh() async {
    setState(() {
      _listsFuture = _loadLists();
    });
  }

  Future<void> _logout() async {
    await ApiService.instance.logout();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('As minhas listas'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Terminar sessão',
            onPressed: _logout,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        icon: const Icon(Icons.add_shopping_cart),
        label: const Text('Nova lista'),
        onPressed: () async {
          await Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const NewListScreen()),
          );
          _refresh();
        },
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<SavedList>>(
          future: _listsFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return _errorView(snapshot.error!);
            }
            final lists = snapshot.data ?? [];
            if (lists.isEmpty) {
              return ListView(
                children: const [
                  SizedBox(height: 120),
                  Icon(Icons.shopping_basket_outlined, size: 48, color: Colors.grey),
                  SizedBox(height: 12),
                  Center(child: Text('Ainda não tem listas guardadas.')),
                ],
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: lists.length,
              separatorBuilder: (_, __) => const Divider(),
              itemBuilder: (context, index) => _listTile(lists[index]),
            );
          },
        ),
      ),
    );
  }

  /// Cada lista do histórico é um dropdown (ExpansionTile): ao tocar,
  /// expande e mostra os itens com uma checkbox cada.
  Widget _listTile(SavedList list) {
    final checked = _checked[list.id] ?? <String>{};
    final total = list.items.length;
    final done = list.items.where(checked.contains).length;

    return ExpansionTile(
      key: PageStorageKey('lista_${list.id}'),
      leading: Icon(
        total > 0 && done == total ? Icons.task_alt : Icons.receipt_long,
      ),
      // Título dado pelo utilizador; sem título, mostra "Lista de dd/mm/aaaa".
      title: Text(
        list.title ?? 'Lista de ${_formatDay(list.createdAt)}',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: list.title == null
            ? const TextStyle(fontStyle: FontStyle.italic)
            : null,
      ),
      subtitle: Text(
        [
          total == 1 ? '1 item' : '$total itens',
          _formatDate(list.createdAt),
          if (total > 0) '$done/$total marcados',
        ].join('  ·  '),
      ),
      // Sem bordas extra: o Divider do ListView já separa as listas.
      shape: const Border(),
      collapsedShape: const Border(),
      childrenPadding: const EdgeInsets.only(left: 8, bottom: 8),
      children: [
        if (list.items.isEmpty)
          const ListTile(
            dense: true,
            title: Text('Esta lista não tem itens.'),
          )
        else
          ...list.items.map((item) {
              final isChecked = checked.contains(item);
              return CheckboxListTile(
                dense: true,
                visualDensity: VisualDensity.compact,
                controlAffinity: ListTileControlAffinity.leading,
                value: isChecked,
                onChanged: (v) => _toggleItem(list.id, item, v ?? false),
                title: Text(
                  _capitalize(item),
                  style: isChecked
                      ? const TextStyle(
                          decoration: TextDecoration.lineThrough,
                          color: Colors.grey,
                        )
                      : null,
                ),
              );
            }),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            icon: const Icon(Icons.edit, size: 18),
            label: Text(list.title == null ? 'Dar título' : 'Mudar título'),
            onPressed: () => _renameList(list),
          ),
        ),
      ],
    );
  }

  /// Distingue sessão inválida (401) de outros erros, como falhas de rede:
  /// no primeiro caso "Tentar novamente" não resolveria, por isso o token
  /// local é apagado e o utilizador volta ao ecrã de autenticação.
  Widget _errorView(Object error) {
    final sessaoInvalida = error is ApiException && error.sessaoInvalida;
    return ListView(
      children: [
        const SizedBox(height: 120),
        const Icon(Icons.error_outline, size: 48, color: Colors.grey),
        const SizedBox(height: 12),
        Center(
          child: Text(
            sessaoInvalida
                ? 'A sessão terminou ou deixou de ser válida.'
                : 'Não foi possível carregar o histórico.\n$error',
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: 12),
        Center(
          child: sessaoInvalida
              ? TextButton(onPressed: _logout, child: const Text('Iniciar sessão'))
              : TextButton(onPressed: _refresh, child: const Text('Tentar novamente')),
        ),
      ],
    );
  }

  String _formatDay(DateTime date) {
    final local = date.toLocal();
    return '${local.day.toString().padLeft(2, '0')}/${local.month.toString().padLeft(2, '0')}/${local.year}';
  }

  String _formatDate(DateTime date) {
    final local = date.toLocal();
    final hh = local.hour.toString().padLeft(2, '0');
    final mm = local.minute.toString().padLeft(2, '0');
    return '${local.day.toString().padLeft(2, '0')}/${local.month.toString().padLeft(2, '0')}/${local.year} · $hh:$mm';
  }

  /// Os itens são guardados em minúsculas pela API ("whole milk");
  /// mostramos a primeira letra em maiúscula para ficar mais legível.
  String _capitalize(String s) =>
      s.isEmpty ? s : '${s[0].toUpperCase()}${s.substring(1)}';
}
