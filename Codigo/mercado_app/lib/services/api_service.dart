import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// Erro simples para mostrar mensagens legíveis na UI.
class ApiException implements Exception {
  final String message;

  /// Código HTTP da resposta, quando o erro veio da API (null em erros de
  /// rede ou de formato da resposta).
  final int? statusCode;
  ApiException(this.message, {this.statusCode});

  /// 401: o token guardado já não é aceite pela API (sessão terminada ou
  /// inválida). Ao contrário de uma falha de rede, repetir o pedido não
  /// resolve; é preciso autenticar de novo.
  bool get sessaoInvalida => statusCode == 401;
  @override
  String toString() => message;
}

/// Um item de uma lista de compras, tal como devolvido pela API.
/// No dataset do projeto os itens são identificados pelo nome
/// (ex.: "whole milk"), por isso mantemos apenas esse campo por agora.
/// Se a API devolver mais campos (categoria, id, etc.), acrescentar aqui.
class ShoppingItem {
  final String name;
  ShoppingItem(this.name);

  factory ShoppingItem.fromJson(dynamic json) {
    if (json is String) return ShoppingItem(json);
    return ShoppingItem(json['name'] ?? json['item'] ?? json.toString());
  }
}

/// Uma lista de compras guardada (histórico do utilizador).
class SavedList {
  final String id;
  /// Título dado pelo utilizador; null se a lista não tiver título.
  final String? title;
  final DateTime createdAt;
  final List<String> items;

  SavedList({required this.id, this.title, required this.createdAt, required this.items});

  factory SavedList.fromJson(Map<String, dynamic> json) {
    final rawTitle = (json['title'] as String?)?.trim();
    return SavedList(
      id: (json['id'] ?? '').toString(),
      title: (rawTitle == null || rawTitle.isEmpty) ? null : rawTitle,
      createdAt: DateTime.tryParse(json['created_at'] ?? '') ?? DateTime.now(),
      // A API devolve cada item como {"item_name": "..."}
      items: List<String>.from(
        (json['items'] ?? []).map((i) => i is String ? i : (i['item_name'] ?? i.toString())),
      ),
    );
  }
}

class ApiService {
  ApiService._internal();
  static final ApiService instance = ApiService._internal();

  static const String baseUrl = 'http://10.0.2.2:8000';

  String? _token;

  Future<void> _loadToken() async {
    if (_token != null) return;
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('auth_token');
  }

  Future<void> _saveToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('auth_token', token);
  }

  Future<void> _clearToken() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
  }

  Future<bool> hasSession() async {
    await _loadToken();
    return _token != null;
  }

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Bearer $_token',
      };

  dynamic _decode(http.Response resp) {
    if (resp.statusCode >= 200 && resp.statusCode < 300) {
      if (resp.body.isEmpty) return null;
      return jsonDecode(resp.body);
    }
    String msg = 'Erro (${resp.statusCode})';
    try {
      final body = jsonDecode(resp.body);
      msg = body['detail']?.toString() ?? msg;
    } catch (_) {}
    throw ApiException(msg, statusCode: resp.statusCode);
  }

  // ---- Autenticação --------------------------------------------------

  Future<void> register(String email, String password, String passwordConfirmation) async {
    final resp = await http.post(
      Uri.parse('$baseUrl/auth/register'),
      headers: _headers,
      // A API exige password_confirmation sem este campo o pedido falha com 422.
      body: jsonEncode({
        'email': email,
        'password': password,
        'password_confirmation': passwordConfirmation,
      }),
    );
    final data = _decode(resp);
    // /auth/register devolve sempre um TokenResponse com login automático.
    final token = data is Map ? data['token'] : null;
    if (token == null) {
      throw ApiException('Resposta de registo inesperada.');
    }
    await _saveToken(token);
  }

  Future<void> login(String email, String password) async {
    final resp = await http.post(
      Uri.parse('$baseUrl/auth/login'),
      headers: _headers,
      body: jsonEncode({'email': email, 'password': password}),
    );
    final data = _decode(resp);
    final token = data is Map ? data['token'] ?? data['access_token'] : null;
    if (token == null) {
      throw ApiException('Resposta de login inesperada.');
    }
    await _saveToken(token);
  }

  Future<void> logout() async {
    await _loadToken();
    try {
      await http.post(Uri.parse('$baseUrl/auth/logout'), headers: _headers);
    } catch (_) {
      // Mesmo que a chamada de rede falhe, terminamos a sessão localmente.
    }
    await _clearToken();
  }

  // ---- Itens e listas --------------------------------------------------

  Future<List<String>> searchItems(String query) async {
    await _loadToken();
    final resp = await http.get(
      Uri.parse('$baseUrl/items').replace(queryParameters: {'search': query}),
      headers: _headers,
    );
    final data = _decode(resp) as List<dynamic>? ?? [];
    return data.map((i) => i is String ? i : (i['name']?.toString() ?? i.toString())).toList();
  }

  Future<List<SavedList>> getLists() async {
    await _loadToken();
    final resp = await http.get(Uri.parse('$baseUrl/lists'), headers: _headers);
    final data = _decode(resp) as List<dynamic>? ?? [];
    return data.map((e) => SavedList.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> saveList(List<String> items, {String? title}) async {
    await _loadToken();
    final cleanTitle = title?.trim();
    final resp = await http.post(
      Uri.parse('$baseUrl/lists'),
      headers: _headers,
      body: jsonEncode({
        'items': items,
        if (cleanTitle != null && cleanTitle.isNotEmpty) 'title': cleanTitle,
      }),
    );
    _decode(resp);
  }

  /// Altera o título de uma lista já guardada (PATCH /lists/{id}).
  /// Um título vazio remove o título.
  Future<void> renameList(String id, String title) async {
    await _loadToken();
    final resp = await http.patch(
      Uri.parse('$baseUrl/lists/$id'),
      headers: _headers,
      body: jsonEncode({'title': title.trim()}),
    );
    _decode(resp);
  }

  Future<List<String>> getRecommendations(List<String> currentItems) async {
    await _loadToken();
    final resp = await http.post(
      Uri.parse('$baseUrl/recommendations'),
      headers: _headers,
      body: jsonEncode({'current_items': currentItems}),
    );
    final data = _decode(resp);
    final list = data is Map ? data['recommended_items'] as List<dynamic>? ?? [] : <dynamic>[];
    return list.map((i) => i is String ? i : (i['name']?.toString() ?? i.toString())).toList();
  }
}
