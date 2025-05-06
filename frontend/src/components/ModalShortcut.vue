<template>
  <v-dialog v-model="dialog" max-width="1000" @keydown.esc="dialog = false">
    <v-card>
      <v-card-title class="mb-2">
        {{ $t("modal.shortcut.title") }}
        <v-spacer></v-spacer>
        <v-text-field
          v-model="search"
          append-icon="mdi-magnify"
          label="Search"
          single-line
          hide-details
          class="mt-0 pt-0"
        ></v-text-field>

        <v-btn icon @click="dialog = false" >
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-data-table
          :headers="headers"
          :items="items"
          :items-per-page="10"
          class="elevation-1"
          :search="search"
        >
          <template v-slot:item.name="{ item }">
            <v-chip class="annotation-chip">
              <v-btn
                disable
                icon
                x-small
                :color="item.color"
                class="mr-1"
              >
                <v-icon>{{ "mdi-palette" }}</v-icon>
              </v-btn>
              {{ item.name }}
            </v-chip>
          </template>
          <template v-slot:item.actions="{ item }">
            <v-text-field
              solo
              flat
              single-line
              hide-details
              @keydown="onKeydown(item, $event)"
              @click:append-outer="clear(item)"
              append-outer-icon="mdi-close"
            >
              <template v-slot:prepend-inner>
                <v-chip v-for="key in item.keys" :key="key">
                  <span>{{ key }}</span>
                </v-chip>
              </template>
            </v-text-field>
          </template>
        </v-data-table>
      </v-card-text>
      <v-card-actions class="pt-0">
        <v-btn class="mr-4" @click="submit" :disable="isSubmitting">
          {{ $t("modal.shortcut.update") }}
        </v-btn>
        <v-btn @click="dialog = false">{{ $t("modal.shortcut.close") }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import Vue from "vue";
import { mapStores } from "pinia";
import { useAnnotationShortcutStore } from "@/store/annotation_shortcut";
import { useShortcutStore } from "@/store/shortcut";
import { useAnnotationStore } from "@/store/annotation";

export default {
  props: ["value"],
  data() {
    return {
      dialog: false,
      isSubmitting: false,
      items: [],
      search: '',
      headers: [
        { text: "Annotation", value: "name" },
        { text: "Shortcut", sortable: false, value: "actions" },
      ],
    };
  },
  computed: {
    annotations() {
      return this.annotationStore.nonTranscripts;
    },
    annotationShortcuts() {
      return this.annotationShortcutStore.all;
    },
    shortcuts() {
      const shortcuts = this.shortcutStore.all;
      return shortcuts;
    },
    ...mapStores(
      useAnnotationShortcutStore,
      useShortcutStore,
      useAnnotationStore
    ),
  },
  methods: {
    onKeydown(item, event) {
      event.preventDefault();
      let newKeys = [];
      if (event.ctrlKey) {
        newKeys.push("Ctrl");
      }
      if (event.shiftKey) {
        newKeys.push("Shift");
      }
      const lowerChar = event.key.toLowerCase();
      if (lowerChar.length === 1) {
        newKeys.push(lowerChar);
      }
      const newShortcut = { ...item, ...{ keys: newKeys } };
      Vue.set(this.items, this.items.indexOf(item), newShortcut);
    },
    clear(item) {
      const newShortcut = { ...item, ...{ keys: [] } };
      Vue.set(this.items, this.items.indexOf(item), newShortcut);
    },

    async submit() {
      if (this.isSubmitting) {
        return;
      }
      this.isSubmitting = true;
      const shortcuts = this.items.map((e) => {
        return { id: e.id, keys: e.keys };
      });

      await this.annotationShortcutStore.update({
        annotationShortcuts: shortcuts,
      });

      this.isSubmitting = false;
      this.dialog = false;
    },
  },
  watch: {
    dialog(value) {
      if (value) {
        this.items = this.annotations;

        let lutAnnotationShortcuts = {};

        this.annotationShortcuts.forEach((e) => {
          lutAnnotationShortcuts[e.annotation_id] = e;
        });

        let lutShortcuts = {};

        this.shortcuts.forEach((e) => {
          lutShortcuts[e.id] = e;
        });

        this.items.forEach((e) => {
          if (lutAnnotationShortcuts[e.id] == null) {
            e.keys = [];
          } else {
            const annotationShortcut = lutAnnotationShortcuts[e.id];
            const shortcut = lutShortcuts[annotationShortcut.shortcut_id];
            e.keys = shortcut.keys;
          }
        });
      }
      this.$emit("input", value);
    },
    value(value) {
      if (value) {
        this.dialog = true;
      }
    },
  },
};
</script>
<style>
.annotation-chip {
  height: auto !important;
}
.annotation-chip .v-chip__content {
  max-width: 100%;
  height: auto;
  min-height: 32px;
  white-space: pre-wrap;
  padding: 5px 0;
}
</style>
