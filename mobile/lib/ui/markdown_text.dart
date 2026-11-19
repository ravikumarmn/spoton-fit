import 'package:material_ui/material_ui.dart';

import 'theme.dart';

/// Renders the small subset of Markdown the coach uses: **bold**, *italic*, bullet and
/// numbered lists, # headings and paragraphs. Anything else shows as plain text, and a
/// half-streamed `**bold` stays plain until its closing `**` arrives.
class MarkdownText extends StatelessWidget {
  const MarkdownText(this.data, {super.key, this.style});
  final String data;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    final base = style ?? AppText.body;
    final children = <Widget>[];
    for (final raw in data.replaceAll('\r\n', '\n').split('\n')) {
      final line = raw.trimRight();
      if (line.trim().isEmpty) {
        if (children.isNotEmpty) children.add(const SizedBox(height: 8));
        continue;
      }
      final bullet = RegExp(r'^\s*[-*•]\s+(.*)$').firstMatch(line);
      final numbered = RegExp(r'^\s*(\d+)[.)]\s+(.*)$').firstMatch(line);
      final heading = RegExp(r'^\s*#{1,6}\s+(.*)$').firstMatch(line);
      if (bullet != null) {
        children.add(_row('•', bullet.group(1)!, base));
      } else if (numbered != null) {
        children.add(_row('${numbered.group(1)}.', numbered.group(2)!, base));
      } else if (heading != null) {
        children.add(
          Text.rich(
            TextSpan(children: parseInline(heading.group(1)!, _bold(base))),
          ),
        );
      } else {
        children.add(Text.rich(TextSpan(children: parseInline(line, base))));
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: children,
    );
  }

  Widget _row(String marker, String text, TextStyle base) => Padding(
    padding: const EdgeInsets.only(left: 4, top: 2),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(width: 22, child: Text(marker, style: base)),
        Expanded(child: Text.rich(TextSpan(children: parseInline(text, base)))),
      ],
    ),
  );
}

TextStyle _bold(TextStyle s) => s.copyWith(
  fontWeight: FontWeight.w700,
  fontVariations: const [FontVariation('wght', 700)],
);

final _inline = RegExp(r'\*\*(.+?)\*\*|\*(.+?)\*');

/// Splits one line into plain, bold and italic spans.
List<InlineSpan> parseInline(String text, TextStyle base) {
  final spans = <InlineSpan>[];
  var last = 0;
  for (final m in _inline.allMatches(text)) {
    if (m.start > last) {
      spans.add(TextSpan(text: text.substring(last, m.start), style: base));
    }
    if (m.group(1) != null) {
      spans.add(TextSpan(text: m.group(1), style: _bold(base)));
    } else {
      spans.add(
        TextSpan(
          text: m.group(2),
          style: base.copyWith(fontStyle: FontStyle.italic),
        ),
      );
    }
    last = m.end;
  }
  if (last < text.length) {
    spans.add(TextSpan(text: text.substring(last), style: base));
  }
  return spans;
}
