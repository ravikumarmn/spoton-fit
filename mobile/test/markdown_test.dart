import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:spoton/ui/markdown_text.dart';

String plain(List<InlineSpan> spans) =>
    spans.map((s) => (s as TextSpan).text).join();

void main() {
  const base = TextStyle(fontSize: 16);

  test('bold and italic markers are removed and styled', () {
    final spans = parseInline(
      'You have **1,854 kcal** and *plenty* of room',
      base,
    );
    expect(plain(spans), 'You have 1,854 kcal and plenty of room');
    final bold = spans.cast<TextSpan>().firstWhere(
      (s) => s.text == '1,854 kcal',
    );
    expect(bold.style!.fontWeight, FontWeight.w700);
    expect(
      spans
          .cast<TextSpan>()
          .firstWhere((s) => s.text == 'plenty')
          .style!
          .fontStyle,
      FontStyle.italic,
    );
  });

  test('an unfinished marker while streaming stays plain text', () {
    expect(plain(parseInline('About **90 kc', base)), 'About **90 kc');
  });

  testWidgets('bullets, numbers and headings render without markers', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: MarkdownText(
            '## Dinner\n\n- **Chicken curry** with 2 chapati\n* Dal and rice\n1. First\n2) Second',
          ),
        ),
      ),
    );
    expect(find.textContaining('##', findRichText: true), findsNothing);
    expect(find.textContaining('**', findRichText: true), findsNothing);
    expect(find.text('Dinner', findRichText: true), findsOneWidget);
    expect(
      find.text('Chicken curry with 2 chapati', findRichText: true),
      findsOneWidget,
    );
    expect(find.text('Dal and rice', findRichText: true), findsOneWidget);
    expect(find.text('•'), findsNWidgets(2));
    expect(find.text('1.'), findsOneWidget);
    expect(find.text('2.'), findsOneWidget);
  });
}
