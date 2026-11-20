import 'package:fl_chart/fl_chart.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/models.dart';
import '../../ui/format.dart';
import '../../ui/theme.dart';

/// Weigh-ins as dots and the smoothed trend as a line. The trend is what targets use.
class WeightChart extends StatelessWidget {
  const WeightChart({super.key, required this.points});
  final List<WeightPoint> points;

  @override
  Widget build(BuildContext context) {
    if (points.length < 2) return const SizedBox.shrink();
    final first = points.first.day;
    double x(DateTime d) => d.difference(first).inDays.toDouble();
    final ys = [
      for (final p in points) ...[p.trendKg, ?p.kg],
    ];
    final lo = (ys.reduce((a, b) => a < b ? a : b) - 1).floorToDouble();
    final hi = (ys.reduce((a, b) => a > b ? a : b) + 1).ceilToDouble();
    final trend = [for (final p in points) FlSpot(x(p.day), p.trendKg)];
    final dots = [
      for (final p in points)
        if (p.kg != null) FlSpot(x(p.day), p.kg!),
    ];
    // Right padding: the last date label ("20 Nov") would otherwise be cut off.
    return Padding(
      padding: const EdgeInsets.only(right: 16),
      child: SizedBox(
        height: 180,
        child: LineChart(
          LineChartData(
            minY: lo,
            maxY: hi,
            lineTouchData: const LineTouchData(enabled: false),
            gridData: const FlGridData(
              drawVerticalLine: false,
              getDrawingHorizontalLine: _gridLine,
            ),
            borderData: FlBorderData(show: false),
            titlesData: FlTitlesData(
              topTitles: const AxisTitles(),
              rightTitles: const AxisTitles(),
              leftTitles: AxisTitles(
                sideTitles: SideTitles(
                  showTitles: true,
                  reservedSize: 40,
                  // A narrow range (a flat trend) needs a decimal, or labels repeat ("92, 92").
                  getTitlesWidget: (v, meta) => (v == meta.min || v == meta.max)
                      ? const SizedBox.shrink()
                      : SideTitleWidget(
                          meta: meta,
                          child: Text(
                            hi - lo <= 4
                                ? v.toStringAsFixed(1)
                                : v.round().toString(),
                            style: AppText.caption,
                          ),
                        ),
                ),
              ),
              bottomTitles: AxisTitles(
                sideTitles: SideTitles(
                  showTitles: true,
                  reservedSize: 24,
                  interval: (x(points.last.day) / 3).clamp(1, 1000).toDouble(),
                  getTitlesWidget: (v, meta) => SideTitleWidget(
                    meta: meta,
                    child: Text(
                      shortDate(first.add(Duration(days: v.round()))),
                      style: AppText.caption,
                    ),
                  ),
                ),
              ),
            ),
            lineBarsData: [
              LineChartBarData(
                spots: dots,
                barWidth: 0,
                color: AppColors.input,
                dotData: FlDotData(
                  getDotPainter: (_, _, _, _) => FlDotCirclePainter(
                    radius: 2.5,
                    color: AppColors.input,
                    strokeWidth: 0,
                  ),
                ),
              ),
              LineChartBarData(
                spots: trend,
                barWidth: 3,
                color: AppColors.primary,
                isStrokeCapRound: true,
                dotData: const FlDotData(show: false),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

FlLine _gridLine(double _) => FlLine(color: AppColors.track, strokeWidth: 1);

/// Bars per day/week/month with a dashed target line. Days without logs show no bar.
class BarsChart extends StatelessWidget {
  const BarsChart({
    super.key,
    required this.values,
    required this.labels,
    required this.color,
    this.target,
    this.height = 150,
  });
  final List<double> values;
  final List<String> labels;
  final Color color;
  final double? target;
  final double height;

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) return const SizedBox.shrink();
    var top = values.reduce((a, b) => a > b ? a : b);
    if (target != null && target! > top) top = target!;
    top = top <= 0 ? 1 : top * 1.15;
    final step = (values.length / 4).ceil().clamp(1, 1000);
    return SizedBox(
      height: height,
      child: BarChart(
        BarChartData(
          maxY: top,
          alignment: BarChartAlignment.spaceAround,
          barTouchData: const BarTouchData(enabled: false),
          gridData: const FlGridData(
            drawVerticalLine: false,
            getDrawingHorizontalLine: _gridLine,
          ),
          borderData: FlBorderData(show: false),
          extraLinesData: target == null
              ? null
              : ExtraLinesData(
                  horizontalLines: [
                    HorizontalLine(
                      y: target!,
                      color: AppColors.text2,
                      strokeWidth: 1.5,
                      dashArray: [5, 4],
                    ),
                  ],
                ),
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(),
            rightTitles: const AxisTitles(),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 40,
                getTitlesWidget: (v, meta) => (v == meta.min || v == meta.max)
                    ? const SizedBox.shrink()
                    : SideTitleWidget(
                        meta: meta,
                        child: Text(fmtInt(v), style: AppText.caption),
                      ),
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 24,
                getTitlesWidget: (v, meta) {
                  final i = v.round();
                  if (i < 0 || i >= labels.length || i % step != 0) {
                    return const SizedBox.shrink();
                  }
                  return SideTitleWidget(
                    meta: meta,
                    child: Text(labels[i], style: AppText.caption),
                  );
                },
              ),
            ),
          ),
          barGroups: [
            for (var i = 0; i < values.length; i++)
              BarChartGroupData(
                x: i,
                barRods: [
                  BarChartRodData(
                    toY: values[i],
                    color: color,
                    width: values.length > 20 ? 5 : 10,
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(3),
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}
