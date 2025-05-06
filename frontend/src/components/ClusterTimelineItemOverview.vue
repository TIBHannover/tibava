<template>
  <v-card v-if="clustersLength == 0" elevation="0" :class="['d-flex', 'flex-column', 'pa-2', 'ma-4']">
    <span>No {{ name }} clustering has been conducted yet. Create it with the <em>{{ name }} Clustering</em> pipeline.</span>
  </v-card>
  <v-virtual-scroll v-else :class="['d-flex', 'flex-column', 'pa-2', 'ma-4']" ref="parentContainer" :items="clusters"
    item-height="140" :bench="clustersLength">
    <template v-slot:default="{ item }">
      <cluster-item-card :type_name="name" :cluster="item" :allClusters="clusters" :key="item.systemId" :ref="`childContainer-${item.systemId}`"></cluster-item-card>
    </template>
  </v-virtual-scroll>
</template>

<script>
import ClusterItemCard from "@/components/ClusterItemCard.vue";

export default {
  props: [ 'clusters', 'name' ],
  computed: {
    clustersLength() {
      return this.clusters.length;
    },
  },
  components: {
    ClusterItemCard,
  }
};
</script>