const rawData = [
  { full: 'HAS_PLUMAGE_TRAIT', short: 'PLUMAGE TRAIT', value: 31155 },
  { full: 'OCCURS_IN', short: 'OCCURS IN', value: 29141 },
  { full: 'INHABITS_BIOME', short: 'BIOME', value: 29064 },
  { full: 'HAS_VOCALIZATION_TYPE', short: 'VOCALIZATION', value: 27906 },
  { full: 'EATS_ITEM', short: 'EATS ITEM', value: 22412 },
  { full: 'THREATENED_BY', short: 'THREATENED BY', value: 13149 },
  { full: 'EATS_CATEGORY', short: 'EATS CATEGORY', value: 12657 },
  { full: 'HAS_IUCN_STATUS', short: 'IUCN STATUS', value: 12419 },
  { full: 'HAS_SEXUAL_DIMORPHISM', short: 'SEXUAL DIMORPHISM', value: 11845 },
  { full: 'HAS_NEST_STRUCTURE', short: 'NEST STRUCTURE', value: 11646 },
  { full: 'HAS_BODY_LENGTH', short: 'BODY LENGTH', value: 11187 },
  { full: 'BREEDS_DURING', short: 'BREEDS DURING', value: 11107 },
  { full: 'HAS_POPULATION_TREND', short: 'POPULATION TREND', value: 10802 },
  { full: 'HAS_MIGRATION_PATTERN', short: 'MIGRATION PATTERN', value: 10145 },
  { full: 'HAS_PARENTAL_ROLE', short: 'PARENTAL ROLE', value: 9799 },
  { full: 'HAS_DIAGNOSTIC_TRAIT', short: 'DIAGNOSTIC TRAIT', value: 9734 },
  { full: 'FORAGES_IN_STRATUM', short: 'FORAGES IN STRATUM', value: 9027 },
  { full: 'HAS_CLUTCH_SIZE', short: 'CLUTCH SIZE', value: 8924 },
  { full: 'HAS_BODY_MASS', short: 'BODY MASS', value: 7894 },
  { full: 'FORAGES_BY', short: 'FORAGES BY', value: 7688 },
  { full: 'NESTS_AT', short: 'NESTS AT', value: 7560 },
  { full: 'HAS_SUBSPECIES', short: 'SUBSPECIES', value: 7317 },
  { full: 'RELATED_TO', short: 'RELATED TO', value: 7147 },
  { full: 'HAS_MOLT_PATTERN', short: 'MOLT PATTERN', value: 7066 },
  { full: 'HAS_STRUCTURE_TRAIT', short: 'STRUCTURE TRAIT', value: 6664 },
  { full: 'HAS_EGG_TRAIT', short: 'EGG TRAIT', value: 5888 },
  { full: 'HAS_CONSERVATION_ACTION', short: 'CONSERVATION ACTION', value: 5763 },
  { full: 'HAS_DISTRIBUTION_NOTE', short: 'DISTRIBUTION NOTE', value: 5635 },
  { full: 'HAS_INCUBATION_PERIOD', short: 'INCUBATION PERIOD', value: 5389 },
  { full: 'HAS_DEMOGRAPHIC_NOTE', short: 'DEMOGRAPHIC NOTE', value: 5353 }
];

const labels = rawData.map(d => d.short);
const fullLabels = rawData.map(d => d.full);
const originalValues = rawData.map(d => d.value);

// =====================================================
// 分段缩放：让中低频 Predicate 不至于被头部高值压扁
// =====================================================
const THRESHOLD = 12000;
const LOW_SCALE = 1.65;
const HIGH_SCALE = 0.26;

function transformValue(v) {
  if (v <= THRESHOLD) {
    return v * LOW_SCALE;
  }
  return THRESHOLD * LOW_SCALE + (v - THRESHOLD) * HIGH_SCALE;
}

function inverseValue(tv) {
  const cut = THRESHOLD * LOW_SCALE;
  if (tv <= cut) {
    return tv / LOW_SCALE;
  }
  return THRESHOLD + (tv - cut) / HIGH_SCALE;
}

const values = originalValues.map(transformValue);
const maxOriginal = Math.max(...originalValues);
const maxTransformed = transformValue(maxOriginal);

// =====================================================
// 颜色工具
// =====================================================
function hexToRgb(hex) {
  hex = hex.replace('#', '');
  if (hex.length === 3) {
    hex = hex.split('').map(c => c + c).join('');
  }
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
// 三套配色方案：默认启用方案 C（墨绿 → 金橙）
// 想换色时，只保留其中一组 colorStart / colorEnd 即可
// =====================================================

// 方案 A：深蓝紫 → 暖珊瑚
// const colorStart = '#4F6BD7';
// const colorEnd = '#F28C6B';

// 方案 B：青蓝 → 紫粉
const colorStart = '#49A6E9';
const colorEnd = '#C86DD7';

// 方案 C：墨绿 → 金橙
// const colorStart = '#2F7F72';
// const colorEnd = '#E7A63A';

const baseColors = rawData.map((_, i) => {
  const t = i / (rawData.length - 1);
  return mixColor(colorStart, colorEnd, t);
});

// =====================================================
// 标签处理：图面使用短标签，多词自动换行
// =====================================================
function wrapShortLabel(str) {
  return str.split(' ').join('\n');
}

option = {
  backgroundColor: '#ffffff',

  title: {
    text: 'High-Frequency Fact Predicate Distribution',
    subtext: 'Top 30 predicates in the current V3 fact graph snapshot',
    left: 'center',
    top: 18,
    textStyle: {
      fontSize: 22,
      fontWeight: 'bold',
      color: '#222'
    },
    subtextStyle: {
      fontSize: 13,
      color: '#666'
    }
  },

  tooltip: {
    trigger: 'item',
    backgroundColor: 'rgba(255, 255, 255, 0.96)',
    borderColor: '#d0d7de',
    borderWidth: 1,
    textStyle: {
      color: '#222',
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
    center: ['50%', '53%'],
    radius: '68%'
  },

  angleAxis: {
    type: 'category',
    data: labels,
    z: 10,
    startAngle: 90,
    axisLine: {
      lineStyle: {
        color: '#aab2bd',
        width: 1
      }
    },
    axisTick: {
      show: false
    },
    axisLabel: {
      interval: 0,
      color: '#333',
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
      color: '#666',
      fontSize: 11,
      formatter: function (value) {
        const approx = Math.round(inverseValue(value));
        return approx.toLocaleString();
      }
    },
    splitLine: {
      lineStyle: {
        color: '#d8dde6',
        type: 'dashed',
        width: 1
      }
    }
  },

  series: [
    {
      type: 'bar',
      coordinateSystem: 'polar',
      roundCap: true,
      barWidth: 18,

      data: values.map((v, i) => ({
        value: v,
        originalValue: originalValues[i],
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: lighten(baseColors[i], 0.32) },
            { offset: 1, color: baseColors[i] }
          ]),
          borderColor: 'rgba(255,255,255,0.65)',
          borderWidth: 0.6
        }
      })),

      label: {
        show: true,
        position: 'outside',
        distance: 2,
        color: '#2b2b2b',
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
          shadowColor: 'rgba(0, 0, 0, 0.18)'
        }
      }
    }
  ]
};