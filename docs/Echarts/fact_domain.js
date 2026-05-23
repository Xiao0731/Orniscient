const domainData = [
  { name: 'MorphologyAndIdentification', value: 217286, share: '24.36%' },
  { name: 'LifeHistoryAndBreeding', value: 137996, share: '15.47%' },
  { name: 'EcologyAndDiet', value: 120624, share: '13.53%' },
  { name: 'DistributionAndMovement', value: 102493, share: '11.49%' },
  { name: 'ConservationAndResearch', value: 85579, share: '9.60%' },
  { name: 'TaxonomyAndPhylogeny', value: 77600, share: '8.70%' },
  { name: 'VocalAndBehavior', value: 76755, share: '8.61%' },
  { name: 'Habitat', value: 73529, share: '8.24%' }
];

const shortName = {
  MorphologyAndIdentification: 'Morphology & ID',
  LifeHistoryAndBreeding: 'Life History & Breeding',
  EcologyAndDiet: 'Ecology & Diet',
  DistributionAndMovement: 'Distribution & Movement',
  ConservationAndResearch: 'Conservation & Research',
  TaxonomyAndPhylogeny: 'Taxonomy & Phylogeny',
  VocalAndBehavior: 'Vocal & Behavior',
  Habitat: 'Habitat'
};

const colors = [
  '#4E79A7',
  '#5B8FF9',
  '#61A0A8',
  '#76B7B2',
  '#8BC6C8',
  '#96C3BE',
  '#9EC4E0',
  '#B8CCE2'
];

const cx = '38%';
const cy = '58%';

option = {
  backgroundColor: '#ffffff',
  color: colors,

  title: [
    {
      text: 'Fact Domain Distribution',
      subtext: 'Final Claim–Fact–Evidence graph · 891,862 Facts',
      left: 'center',
      top: 20,
      textStyle: {
        fontSize: 26,
        fontWeight: 'bold',
        color: '#222'
      },
      subtextStyle: {
        fontSize: 13,
        color: '#666'
      }
    },
    {
      text: '8\nDomains',
      left: cx,
      top: cy,
      textAlign: 'center',
      textVerticalAlign: 'middle',
      itemGap: 2,
      textStyle: {
        fontSize: 18,
        lineHeight: 24,
        fontWeight: 'bold',
        color: '#444'
      }
    }
  ],

  tooltip: {
    trigger: 'item',
    formatter: function (params) {
      const item = domainData.find(d => d.name === params.name);
      return `
        <b>${shortName[params.name] || params.name}</b><br/>
        Fact Count: ${params.value.toLocaleString()}<br/>
        Share: ${item ? item.share : params.percent + '%'}
      `;
    }
  },

  legend: {
    type: 'scroll',
    orient: 'vertical',
    right: '2%',
    top: 'middle',
    itemWidth: 14,
    itemHeight: 14,
    textStyle: {
      fontSize: 12,
      color: '#333'
    },
    formatter: function (name) {
      const item = domainData.find(d => d.name === name);
      const label = shortName[name] || name;
      return item ? `${label}  ${item.share}` : label;
    }
  },

  series: [
    {
      name: 'Fact Domain',
      type: 'pie',
      radius: ['42%', '68%'],
      center: [cx, cy],
      minAngle: 4,
      avoidLabelOverlap: true,

      itemStyle: {
        borderColor: '#fff',
        borderWidth: 2,
        borderRadius: 8
      },

      label: {
        show: true,
        formatter: function (params) {
          const item = domainData.find(d => d.name === params.name);
          return `${shortName[params.name] || params.name}\n${item ? item.share : params.percent + '%'}`;
        },
        fontSize: 11,
        lineHeight: 16,
        color: '#333'
      },

      labelLine: {
        show: true,
        length: 14,
        length2: 12,
        smooth: 0.2
      },

      emphasis: {
        scale: true,
        scaleSize: 6,
        itemStyle: {
          shadowBlur: 12,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.18)'
        }
      },

      data: domainData
    }
  ]
};