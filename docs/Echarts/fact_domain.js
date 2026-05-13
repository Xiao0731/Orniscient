const domainData = [
  { name: 'MorphologyAndIdentification', value: 89896, share: '21.31%' },
  { name: 'LifeHistoryAndBreeding', value: 73143, share: '17.34%' },
  { name: 'DistributionAndMovement', value: 57427, share: '13.61%' },
  { name: 'EcologyAndDiet', value: 53310, share: '12.64%' },
  { name: 'ConservationAndResearch', value: 50642, share: '12.00%' },
  { name: 'VocalAndBehavior', value: 37339, share: '8.85%' },
  { name: 'Habitat', value: 33364, share: '7.91%' },
  { name: 'TaxonomyAndPhylogeny', value: 26761, share: '6.34%' }
];

const shortName = {
  MorphologyAndIdentification: 'Morphology & ID',
  LifeHistoryAndBreeding: 'Life History & Breeding',
  DistributionAndMovement: 'Distribution & Movement',
  EcologyAndDiet: 'Ecology & Diet',
  ConservationAndResearch: 'Conservation & Research',
  VocalAndBehavior: 'Vocal & Behavior',
  Habitat: 'Habitat',
  TaxonomyAndPhylogeny: 'Taxonomy & Phylogeny'
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
      subtext: 'Current V3 fact graph snapshot',
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
      return `
        <b>${shortName[params.name] || params.name}</b><br/>
        Fact Count: ${params.value.toLocaleString()}<br/>
        Share: ${params.percent}%
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
      return shortName[name] || name;
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
          return `${shortName[params.name] || params.name}\n${params.percent}%`;
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
        scaleSize: 6
      },
      data: domainData
    }
  ]
};