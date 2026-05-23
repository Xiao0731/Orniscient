const rawData = [
  { full: 'HAS_PLUMAGE_TRAIT', short: 'PLUMAGE TRAIT', value: 88726 },
  { full: 'INHABITS_BIOME', short: 'BIOME', value: 61235 },
  { full: 'OCCURS_IN', short: 'OCCURS IN', value: 49913 },
  { full: 'EATS_ITEM', short: 'EATS ITEM', value: 49404 },
  { full: 'HAS_VOCALIZATION_TYPE', short: 'VOCALIZATION', value: 42121 },
  { full: 'HAS_SUBSPECIES', short: 'SUBSPECIES', value: 31396 },
  { full: 'THREATENED_BY', short: 'THREATENED BY', value: 21709 },
  { full: 'HAS_NEST_STRUCTURE', short: 'NEST STRUCTURE', value: 20342 },
  { full: 'HAS_DIAGNOSTIC_TRAIT', short: 'DIAGNOSTIC TRAIT', value: 19945 },
  { full: 'EATS_CATEGORY', short: 'EATS CATEGORY', value: 19633 },
  { full: 'HAS_PARENTAL_ROLE', short: 'PARENTAL ROLE', value: 19075 },
  { full: 'FORAGES_IN_STRATUM', short: 'FORAGES IN STRATUM', value: 18980 },
  { full: 'HAS_POPULATION_TREND', short: 'POPULATION TREND', value: 18817 },
  { full: 'FORAGES_BY', short: 'FORAGES BY', value: 18706 },
  { full: 'HAS_STRUCTURE_TRAIT', short: 'STRUCTURE TRAIT', value: 17377 },
  { full: 'HAS_SEXUAL_DIMORPHISM', short: 'SEXUAL DIMORPHISM', value: 16829 },
  { full: 'HAS_BODY_LENGTH', short: 'BODY LENGTH', value: 16534 },
  { full: 'BREEDS_DURING', short: 'BREEDS DURING', value: 16496 },
  { full: 'HAS_BODY_MASS', short: 'BODY MASS', value: 15763 },
  { full: 'HAS_DISTRIBUTION_NOTE', short: 'DISTRIBUTION NOTE', value: 15370 },
  { full: 'HAS_IUCN_STATUS', short: 'IUCN STATUS', value: 15166 },
  { full: 'RELATED_TO', short: 'RELATED TO', value: 14646 },
  { full: 'HAS_MIGRATION_PATTERN', short: 'MIGRATION PATTERN', value: 14634 },
  { full: 'HAS_DEMOGRAPHIC_NOTE', short: 'DEMOGRAPHIC NOTE', value: 13663 },
  { full: 'NESTS_AT', short: 'NESTS AT', value: 13002 },
  { full: 'HAS_CONSERVATION_ACTION', short: 'CONSERVATION ACTION', value: 12263 },
  { full: 'USES_MICROHABITAT', short: 'MICROHABITAT', value: 12021 },
  { full: 'HAS_TAXONOMIC_NOTE', short: 'TAXONOMIC NOTE', value: 11924 },
  { full: 'HAS_MOLT_PATTERN', short: 'MOLT PATTERN', value: 11839 },
  { full: 'HAS_CLUTCH_SIZE', short: 'CLUTCH SIZE', value: 11635 }
];

const labels = rawData.map(d => d.short);
const fullLabels = rawData.map(d => d.full);
const originalValues = rawData.map(d => d.value);

// =====================================================
// 分段缩放：避免头部 Predicate 把中低频 Predicate 压扁
// =====================================================
const THRESHOLD = 12000;
const LOW_SCALE = 1.65;
const HIGH_SCALE = 0.26;

function transformValue(v) {
  if (v <= THRESHOLD) return v * LOW_SCALE;
  return THRESHOLD * LOW_SCALE + (v - THRESHOLD) * HIGH_SCALE;
}

function inverseValue(tv) {
  const cut = THRESHOLD * LOW_SCALE;
  if (tv <= cut) return tv / LOW_SCALE;
  return THRESHOLD + (tv - cut) / HIGH_SCALE;
}

const values = originalValues.map(transformValue);
const maxOriginal = Math.max(...originalValues);
const maxTransformed = transformValue(maxOriginal);

// =====================================================
// 配色工具
// =====================================================
function hexToRgb(hex) {
  hex = hex.replace('#', '');
  if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
  const num = parseInt(hex, 16);
  return {
    r: (num >> 16) & 255,
    g: (num >> 8) & 255,
    b: num & 255
  };
}

function rgbToHex(r, g, b) {
  return (
    '#' +
    [r, g, b]
      .map(x => {
        const h = x.toString(16);
        return h.length === 1 ? '0' + h : h;
      })
      .join('')
  );
}

function mixColor(c1, c2, t) {
  const a = hexToRgb(c1);
  const b = hexToRgb(c2);
  const r = Math.round(a.r + (b.r - a.r) * t);
  const g = Math.round(a.g + (b.g - a.g) * t);
  const bb = Math.round(a.b + (b.b - a.b) * t);
  return rgbToHex(r, g, bb);
}

function lighten(hex, factor = 0.28) {
  const c = hexToRgb(hex);
  const r = Math.round(c.r + (255 - c.r) * factor);
  const g = Math.round(c.g + (255 - c.g) * factor);
  const b = Math.round(c.b + (255 - c.b) * factor);
  return rgbToHex(r, g, b);
}

// =====================================================
// 低饱和蓝灰 / 青绿配色，统一 taxonomy / checklist 图风格
// =====================================================
const paletteStops = [
  '#1F3D55',  // 深蓝灰
  '#2F6F7E',  // 深青绿
  '#3F8492',  // 中青
  '#6EA8B7',  // 浅青蓝
  '#A9C9DA'   // 雾蓝
];

// 方案 A：深蓝紫 → 暖珊瑚
// const colorStart = '#4F6BD7';
// const colorEnd = '#F28C6B';

// 方案 B：青蓝 → 紫粉
// const colorStart = '#49A6E9';
// const colorEnd = '#C86DD7';

// 方案 C：墨绿 → 金橙
// const colorStart = '#2F7F72';
// const colorEnd = '#E7A63A';

function gradientPalette(i, n) {
  const t = i / Math.max(1, n - 1);
  const segment = 1 / (paletteStops.length - 1);
  const idx = Math.min(
    paletteStops.length - 2,
    Math.floor(t / segment)
  );
  const localT = (t - idx * segment) / segment;
  return mixColor(paletteStops[idx], paletteStops[idx + 1], localT);
}

const baseColors = rawData.map((_, i) => gradientPalette(i, rawData.length));

function wrapShortLabel(str) {
  return str.split(' ').join('\n');
}

option = {
  backgroundColor: '#ffffff',

  title: {
    text: 'High-Frequency Fact Predicate Distribution',
    subtext: 'Top 30 predicates in the final Claim–Fact–Evidence graph',
    left: 'center',
    top: 18,
    textStyle: {
      fontSize: 24,
      fontWeight: 600,
      color: '#1F2933'
    },
    subtextStyle: {
      fontSize: 13,
      color: '#667085'
    }
  },

  tooltip: {
    trigger: 'item',
    backgroundColor: 'rgba(255, 255, 255, 0.97)',
    borderColor: '#C7D3DD',
    borderWidth: 1,
    extraCssText: 'box-shadow: 0 8px 24px rgba(31, 61, 85, 0.12);',
    textStyle: {
      color: '#243447',
      fontSize: 13
    },
    formatter: function (params) {
      const idx = params.dataIndex;
      return `
        <b>${fullLabels[idx]}</b><br/>
        Fact Count: ${originalValues[idx].toLocaleString()}
      `;
    }
  },

  polar: {
    center: ['50%', '54%'],
    radius: '68%'
  },

  angleAxis: {
    type: 'category',
    data: labels,
    z: 10,
    startAngle: 90,

    axisLine: {
      lineStyle: {
        color: '#9AA9B8',
        width: 1
      }
    },

    axisTick: {
      show: false
    },

    axisLabel: {
      interval: 0,
      color: '#2F3A45',
      fontSize: 9,
      lineHeight: 11,
      margin: 15,
      formatter: function (value) {
        return wrapShortLabel(value);
      }
    }
  },

  radiusAxis: {
    min: 0,
    max: maxTransformed,
    splitNumber: 5,

    axisLine: {
      show: false
    },

    axisTick: {
      show: false
    },

    axisLabel: {
      color: '#667085',
      fontSize: 10,
      formatter: function (value) {
        const approx = Math.round(inverseValue(value));
        if (approx >= 1000) return (approx / 1000).toFixed(0) + 'k';
        return approx.toLocaleString();
      }
    },

    splitLine: {
      lineStyle: {
        color: '#D9E2EA',
        type: 'dashed',
        width: 1
      }
    }
  },

  series: [
    {
      name: 'Fact Predicate',
      type: 'bar',
      coordinateSystem: 'polar',
      roundCap: true,
      barWidth: 17,

      data: values.map((v, i) => ({
        value: v,
        originalValue: originalValues[i],
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: lighten(baseColors[i], 0.35) },
            { offset: 1, color: baseColors[i] }
          ]),
          borderColor: 'rgba(255,255,255,0.75)',
          borderWidth: 0.7
        }
      })),

      label: {
        show: true,
        position: 'outside',
        distance: 2,
        color: '#26323D',
        fontSize: 8,
        formatter: function (params) {
          const v = params.data.originalValue;
          return v >= 10000
            ? (v / 1000).toFixed(1) + 'k'
            : v.toLocaleString();
        }
      },

      emphasis: {
        focus: 'series',
        itemStyle: {
          shadowBlur: 12,
          shadowColor: 'rgba(31, 61, 85, 0.20)'
        }
      }
    }
  ],

  graphic: [
    {
      type: 'text',
      left: 'center',
      top: '52%',
      style: {
        text: 'Top 30\nPredicates',
        textAlign: 'center',
        fill: '#2F3A45',
        fontSize: 18,
        fontWeight: 600,
        lineHeight: 26
      }
    }
  ]
};