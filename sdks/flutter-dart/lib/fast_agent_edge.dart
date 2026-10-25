// fast_agent_edge.dart
// Drop-in Edge Agent Engine client library for Flutter desktop applications.

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

/// Diagnostic status of the local edge engine.
class FastAgentStatus {
  final String status;
  final String modelPath;
  final double engineRssMb;
  final int memoryBudgetMb;
  final int activeSlots;
  final String licenseTier;

  FastAgentStatus({
    required this.status,
    required this.modelPath,
    required this.engineRssMb,
    required this.memoryBudgetMb,
    required this.activeSlots,
    required this.licenseTier,
  });

  factory FastAgentStatus.fromJson(Map<String, dynamic> json) {
    final mem = json['memory'] as Map<String, dynamic>? ?? {};
    final slots = json['slots'] as Map<String, dynamic>? ?? {};
    final lic = json['license'] as Map<String, dynamic>? ?? {};
    return FastAgentStatus(
      status: json['status'] ?? 'unknown',
      modelPath: json['model_path'] ?? '',
      engineRssMb: (mem['engine_rss_mb'] as num?)?.toDouble() ?? 0.0,
      memoryBudgetMb: (mem['engine_budget_mb'] as num?)?.toInt() ?? 0,
      activeSlots: (slots['active_count'] as num?)?.toInt() ?? 0,
      licenseTier: lic['tier'] ?? 'COMMUNITY',
    );
  }
}

/// Result of a single agent turn.
class AgentTurnResult {
  final String output;
  final dynamic parsedJson;
  final String sessionId;
  final double promptEvalMs;
  final int turnCount;

  AgentTurnResult({
    required this.output,
    this.parsedJson,
    required this.sessionId,
    required this.promptEvalMs,
    required this.turnCount,
  });

  factory AgentTurnResult.fromJson(Map<String, dynamic> json) {
    return AgentTurnResult(
      output: json['output'] ?? '',
      parsedJson: json['parsed_json'],
      sessionId: json['session_id'] ?? 'default',
      promptEvalMs: (json['prompt_eval_ms'] as num?)?.toDouble() ?? 0.0,
      turnCount: (json['turn_count'] as num?)?.toInt() ?? 1,
    );
  }
}

/// FastAgent client for Flutter desktop applications.
class FastAgentClient {
  final String baseUrl;
  final http.Client _httpClient;

  FastAgentClient({this.baseUrl = 'http://127.0.0.1:8085', http.Client? client})
      : _httpClient = client ?? http.Client();

  /// Scopes requests to an isolated document or tab slot.
  FastAgentTabSession session(String sessionId) {
    return FastAgentTabSession(client: this, sessionId: sessionId);
  }

  /// Checks if the local engine is responsive and returns metrics.
  Future<FastAgentStatus> getStatus() async {
    final res = await _httpClient.get(Uri.parse('$baseUrl/v1/status'));
    if (res.statusCode == 200) {
      return FastAgentStatus.fromJson(jsonDecode(res.body));
    }
    throw HttpException('Engine error: HTTP ${res.statusCode}');
  }

  /// Executes single turn with slot caching.
  Future<AgentTurnResult> turn({
    required String prompt,
    String sessionId = 'default',
    int maxTokens = 160,
    double temperature = 0.1,
    String? grammar,
    Map<String, dynamic>? jsonSchema,
  }) async {
    final payload = {
      'prompt': prompt,
      'session_id': sessionId,
      'max_tokens': maxTokens,
      'temperature': temperature,
      'grammar': grammar,
      'json_schema': jsonSchema,
    };

    final res = await _httpClient.post(
      Uri.parse('$baseUrl/v1/agent/turn'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );

    if (res.statusCode == 200) {
      return AgentTurnResult.fromJson(jsonDecode(res.body));
    }
    throw HttpException('Turn error: ${res.body}');
  }

  /// Extracts structured JSON conforming strictly to the provided JSON Schema.
  Future<dynamic> runStructured({
    required String prompt,
    required Map<String, dynamic> jsonSchema,
    String sessionId = 'default',
  }) async {
    final result = await turn(
      prompt: prompt,
      sessionId: sessionId,
      jsonSchema: jsonSchema,
    );
    return result.parsedJson;
  }

  /// Streams token-by-token generation for real-time Flutter UI rendering.
  Stream<String> streamChat({
    required String prompt,
    String sessionId = 'default',
    String? grammar,
    Map<String, dynamic>? jsonSchema,
  }) async* {
    final request = http.Request(
      'POST',
      Uri.parse('$baseUrl/v1/chat/completions'),
    );
    request.headers['Content-Type'] = 'application/json';
    request.body = jsonEncode({
      'prompt': prompt,
      'stream': true,
      'session_id': sessionId,
      'grammar': grammar,
      'json_schema': jsonSchema,
    });

    final streamedResponse = await _httpClient.send(request);
    final lines = streamedResponse.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter());

    await for (final line in lines) {
      final trimmed = line.trim();
      if (trimmed.startsWith('data: ')) {
        final data = trimmed.substring(6);
        if (data == '[DONE]') break;
        try {
          final decoded = jsonDecode(data);
          final token = decoded['choices']?[0]?['delta']?['content'];
          if (token != null && token is String) {
            yield token;
          }
        } catch (_) {}
      }
    }
  }

  /// Runs autonomous multi-step problem solving.
  Future<String> ask({
    required String prompt,
    String sessionId = 'default',
    int maxSteps = 5,
  }) async {
    final res = await _httpClient.post(
      Uri.parse('$baseUrl/v1/agent/ask'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'prompt': prompt,
        'session_id': sessionId,
        'max_steps': maxSteps,
      }),
    );

    if (res.statusCode == 200) {
      final body = jsonDecode(res.body);
      return body['result'] ?? '';
    }
    throw HttpException('Ask error: ${res.body}');
  }
}

/// Tab-scoped session helper for multi-tab Flutter desktop apps.
class FastAgentTabSession {
  final FastAgentClient client;
  final String sessionId;

  FastAgentTabSession({required this.client, required this.sessionId});

  Future<AgentTurnResult> turn(String prompt, {Map<String, dynamic>? jsonSchema}) {
    return client.turn(prompt: prompt, sessionId: sessionId, jsonSchema: jsonSchema);
  }

  Stream<String> stream(String prompt) {
    return client.streamChat(prompt: prompt, sessionId: sessionId);
  }

  Future<String> ask(String prompt, {int maxSteps = 5}) {
    return client.ask(prompt: prompt, sessionId: sessionId, maxSteps: maxSteps);
  }
}
