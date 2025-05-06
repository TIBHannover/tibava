<template>
  <div>
    <v-dialog v-model="show" width="90%" persistent>
      <template v-slot:activator="{ on, attrs }">
        <v-btn v-bind="attrs" v-on="on" text block large>
          <v-icon left>{{ "mdi-eye-outline" }}</v-icon>
          {{ $t("button.edit") }}
        </v-btn>
      </template>
      <v-card v-show="show" class="canvasContainer" ref="canvasContainer">
        <v-card-title>Cluster {{ this.cluster.name }} </v-card-title>
        <v-card-subtitle>Click on images to mark them for deletion. There are {{ cluster.items.length }} images in total.</v-card-subtitle>
        <v-virtual-scroll
          :items="items"
          height="600px"
          item-height="170px"
        >
          <template v-slot:default="{ item }">
            <v-list-item :key="item.name">
              <v-list-item-content>
                <v-list-item-title>
                  {{ item.name }}
                </v-list-item-title>
                <div style="display: flex; overflow-y: auto; padding: 5px 0;">
                  <img class="clusterImg" v-for="imageUrl in item.visibleImages" :key="imageUrl" :src="imageUrl"
                    :style="borderStyle(imageUrl)" @click="mark(imageUrl)" loading="lazy"/>
                </div>
              </v-list-item-content>
              <v-list-item-action>
                <v-btn
                  v-if="!item.show"
                  icon
                  @click="showItems(item)"
                >
                  <v-icon x-large>mdi-chevron-right</v-icon>
                </v-btn>
              </v-list-item-action>
            </v-list-item>
            <v-divider></v-divider>
          </template>
        </v-virtual-scroll>
        <v-card-actions variant="tonal">
          <v-btn @click="abort"> {{ $t("button.cancel") }} </v-btn>
          <v-spacer></v-spacer>
          <v-btn :disabled="!imagesSelectedForDeletion" @click="showConfirmation = true">
            {{ $t("button.delete") }}
          </v-btn>
          <v-btn :disabled="!imagesSelectedForDeletion" @click="showNewCluster = true">
            {{ $t('modal.cluster_edit.new_cluster') }}
          </v-btn>
          <v-btn :disabled="!imagesSelectedForDeletion" @click="showMove = true">
            {{ $t('modal.cluster_edit.move') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="showConfirmation" width="auto">
      <v-card>
        <v-card-title>
          Confirm
        </v-card-title>
        <v-card-text>
          Delete {{ this.markedForDeletion.length }} images from Cluster "{{ this.cluster.name }}"?
          <v-card-text style="color: red" v-if="allImagesMarked"> <b>You selected all images. This removes the
              cluster.</b></v-card-text>
        </v-card-text>
        <v-card-actions>
          <v-btn @click="showConfirmation = false"> Back </v-btn>
          <v-spacer></v-spacer>
          <v-btn @click="applyDeletion"> Confirm </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="showMove" width="300px">
      <v-card>
        <v-card-title>
          {{ $t('modal.cluster_edit.move_existing') }}
        </v-card-title>
        <v-card-text>
          <v-list dense>
            <v-subheader>Clusters</v-subheader>
            <v-list-item-group
              v-model="toMoveCluster"
              color="primary"
              style="max-height: 500px; overflow-x: auto;"
            >
              <v-list-item
                v-for="cluster in allClustersButSelf"
                :key="cluster.id"
              >
                <v-list-item-content>
                  <v-list-item-title>{{ cluster.name }}</v-list-item-title>
                </v-list-item-content>
              </v-list-item>
            </v-list-item-group>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-btn @click="showMove = false">{{  $t('button.cancel') }}</v-btn>
          <v-spacer></v-spacer>
          <v-btn :disabled="toMoveCluster === undefined" @click="applyMove">{{ $t('modal.cluster_edit.move') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="showNewCluster" width="300px">
      <v-card>
        <v-card-title>
          {{ $t('modal.cluster_edit.move_new') }}
        </v-card-title>
        <v-card-text>
          <v-text-field
            label="Cluster Name"
            v-model="newClusterName"
          ></v-text-field>
        </v-card-text>
        <v-card-actions>
          <v-btn @click="showNewCluster = false">{{ $t('button.cancel') }}</v-btn>
          <v-spacer></v-spacer>
          <v-btn :disabled="newClusterName.length == 0" @click="applyNewCluster">{{ $t('button.create') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script>
import { mapStores } from "pinia";
import { useClusterTimelineItemStore } from '../store/cluster_timeline_item';
import { useShotStore } from '../store/shot';

export default {
  props: ["cluster", "allClusters"],
  data() {
    return {
      show: false,
      showConfirmation: false,
      showNewCluster: false,
      newClusterName: '',
      showMove: false,
      toMoveCluster: undefined,
      markedForDeletion: [],
      items: []
    };
  },
  methods: {
    showItems(item) {
      item.show = true;
      item.visibleImages = item.images;
    },
    marked(imageUrl) {
      return this.markedForDeletion.includes(imageUrl);
    },
    mark(imageUrl) {
      if (this.marked(imageUrl)) {
        this.markedForDeletion = this.markedForDeletion.filter((e) => e != imageUrl);
      } else {
        this.markedForDeletion.push(imageUrl);
      }
    },
    borderStyle(imageUrl) {
      if (this.marked(imageUrl)) {
        return 'border: 5px solid red'
      }
      return ''
    },
    async applyMove() {
      const marked_items = this.cluster.items.filter((i) => this.markedForDeletion.includes(i.image_path))
                                             .map((i) => i.id);
      await this.clusterTimelineItemStore.moveItemsToCluster(
        this.cluster.cluster_id,
        marked_items,
        this.allClustersButSelf[this.toMoveCluster].cluster_id
      );
      this.show = false;
      this.markedForDeletion = [];
      this.showMove = false;
      if (this.allImagesMarked) {
        this.$emit("deleteCluster");
      }
    },
    async applyNewCluster() {
      const marked_items = this.cluster.items.filter((i) => this.markedForDeletion.includes(i.image_path))
                                             .map((i) => i.id);
      const newCluster = await this.clusterTimelineItemStore.create(
        this.newClusterName,
        this.cluster.video,
        this.cluster.plugin_run,
        this.cluster.type
      )
      if (newCluster) {
        await this.clusterTimelineItemStore.moveItemsToCluster(
          this.cluster.cluster_id,
          marked_items,
          newCluster.cluster_id
        );
      }
      this.show = false;
      this.markedForDeletion = [];
      this.newClusterName = '';
      this.showNewCluster = false;
      if (this.allImagesMarked) {
        this.$emit("deleteCluster");
      }
    },
    async applyDeletion() {
      const item_ids_to_delete = this.cluster.items.filter((i) => this.markedForDeletion.includes(i.image_path))
                                                   .map((i) => i.id);
      await this.clusterTimelineItemStore.deleteItems(this.cluster.cluster_id, item_ids_to_delete);

      this.markedForDeletion = [];
      this.showConfirmation = false;
      this.show = false;
      if (this.allImagesMarked) {
        this.$emit("deleteCluster");
      }
    },
    abort() {
      this.markedForDeletion = [];
      this.show = false;
    },
    generateItems() {
      this.items = this.shotStore.shots.map((shot, i) => {
        const images = this.cluster.items.filter((i) => Math.round(shot.start) <= Math.round(i.time) && Math.round(i.time) < Math.round(shot.end)).map((i) => i.image_path);
        return {
          name: "Shot " + i,
          images: images,
          start: shot.start,
          end: shot.end,
          visibleImages: images.slice(0, 5),
          show: images.length <= 5
        };
      }).filter((s) => s.images.length > 0);
    },
  },
  created() {
    this.generateItems();
  },
  computed: {
    allImagesMarked() {
      return this.markedForDeletion.length === this.items.length;
    },
    imagesSelectedForDeletion() {
      return this.markedForDeletion.length > 0;
    },
    allClustersButSelf() {
      return this.allClusters.filter((c) => c.id !== this.cluster.id);
    },
    ...mapStores(useClusterTimelineItemStore, useShotStore),
  },
  watch: {
    'shotStore.shots': function() {
      this.generateItems();
    },
    'cluster.items': function() {
      this.generateItems();
    }
  }
};
</script>

<style>
.scrollable-content {
  max-height: 70vh;
  margin-bottom: 5px;
}

.clusterImg {
  margin: 5px;
  height: 100px;
}

.canvasContainer {
  background: white;
}
</style>