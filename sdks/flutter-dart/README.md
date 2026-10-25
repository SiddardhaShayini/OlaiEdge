# fast_agent_edge (Flutter Desktop)

Drop-in Edge Agent Engine client library for Flutter desktop applications (Windows, macOS, Linux).

## Features

- **Stream Chat UI:** `Stream<String>` integration directly into Flutter `StreamBuilder`.
- **Zero Cloud Costs:** Offline local LLM inference without API latency or recurring bills.
- **Tab Slot Caching:** Tab-scoped sessions maintain instant prefix caching across documents.
- **Strict JSON Parsing:** Automatic schema validation for app models.

## Usage in Flutter Desktop

```dart
import 'package:flutter/material.dart';
import 'package:fast_agent_edge/fast_agent_edge.dart';

final client = FastAgentClient(baseUrl: 'http://127.0.0.1:8085');

class NoteAIAssistant extends StatefulWidget {
  final String noteId;
  const NoteAIAssistant({Key? key, required this.noteId}) : super(key: key);

  @override
  _NoteAIAssistantState createState() => _NoteAIAssistantState();
}

class _NoteAIAssistantState extends State<NoteAIAssistant> {
  String _responseBuffer = "";

  void _summarizeNote(String noteContent) {
    setState(() => _responseBuffer = "");
    
    // Tab-isolated session with LCP prompt caching
    final session = client.session(widget.noteId);
    
    session.stream("Summarize: $noteContent").listen(
      (token) {
        setState(() {
          _responseBuffer += token;
        });
      },
      onDone: () => print("Streaming completed!"),
      onError: (err) => print("Error: $err"),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        ElevatedButton(
          onPressed: () => _summarizeNote("Sample meeting notes..."),
          child: const Text("Generate AI Summary"),
        ),
        Text(_responseBuffer),
      ],
    );
  }
}
```
