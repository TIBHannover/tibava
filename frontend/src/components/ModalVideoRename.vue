<template>
  <v-dialog v-model="show" max-width="1000">
    <template v-slot:activator="{ on }">
      <slot name="activator" v-bind="on">
        <v-btn v-on="on" text block large>
          <v-icon left>{{ "mdi-pencil" }}</v-icon>
          {{ $t("modal.video.rename.link") }}
        </v-btn>
      </slot>
    </template>
    <v-card>
      <v-card-title class="mb-2">
        {{ $t("modal.video.rename.title") }}

        <v-btn icon @click.native="show = false" absolute top right>
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-text-field
          :label="$t('modal.video.rename.name')"
          prepend-icon="mdi-pencil"
          v-model="name"
        ></v-text-field>
      </v-card-text>
      <v-card-actions class="pt-0">
        <v-btn class="mr-4" @click="submit" :disabled="isSubmitting || !name">
          {{ $t("modal.video.rename.update") }}
        </v-btn>
        <v-btn @click="show = false">{{
          $t("modal.video.rename.close")
        }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapStores } from "pinia";
import { useVideoStore } from "@/store/video";

export default {
  props: ["video"],
  data() {
    return {
      show: false,
      isSubmitting: false,
      nameProxy: null,
      items: [],
    };
  },
  computed: {
    name: {
      get() {
        const name = this.videoStore.get(this.video).name;
        return this.nameProxy === null ? name : this.nameProxy;
      },
      set(val) {
        this.nameProxy = val;
      },
    },
    ...mapStores(useVideoStore),
  },
  methods: {
    async submit() {
      if (this.isSubmitting) {
        return;
      }
      this.isSubmitting = true;

      await this.videoStore.rename({
        videoId: this.video,
        name: this.name,
      });

      this.isSubmitting = false;
      this.show = false;
    },
  },
  watch: {
    show(value) {
      if (value) {
        this.nameProxy = null;
        this.$emit("close");
      }
    },
  },
};
</script>
