<template>
  <v-dialog persistent :value="show" max-width="1000" @keydown.esc="close">
    <v-card>
      <v-toolbar color="primary" dark>
        {{ $t("timelineSegment.title") }}
      </v-toolbar>
      <v-card-text>
        <v-form @submit.prevent="submit">
          <v-combobox
            v-if="show"
            clearable
            multiple
            autofocus
            v-model="annotations"
            :items="allExistingAnnotations"
            :search-input.sync="search"
            @change="onAnnotationChange"
            @keydown="onKeydown"
            item-text="name"
            class="mb-9"
          >
            <template v-slot:no-data>
              <v-list-item>
                <v-list-item-content>
                  <v-list-item-title>
                    No results matching "<strong>{{ search }}</strong
                    >". Press <kbd>enter</kbd> to create a new one
                  </v-list-item-title>
                </v-list-item-content>
              </v-list-item>
            </template>

            <template v-slot:item="{ item }">
              <v-chip>
                <v-btn disabled icon x-small :color="item.color" class="mr-1">
                  <v-icon>mdi-palette</v-icon>
                </v-btn>
                <v-btn
                  v-if="item.category"
                  disabled
                  x-small
                  :color="item.category.color || item.color"
                  class="mr-1"
                >
                  {{ item.category.name }}
                </v-btn>
                <span>{{ item.name }}</span>
              </v-chip>
            </template>

            <template v-slot:selection="{ item, index }">
              <v-chip>
                <v-menu
                  v-model="item.colorMenu"
                  top
                  nudge-bottom="105"
                  nudge-left="16"
                  :close-on-content-click="false"
                >
                  <template v-slot:activator="{ on, attrs }">
                    <v-btn
                      icon
                      x-small
                      :color="item.color"
                      class="mr-1"
                      v-bind="attrs"
                      v-on="on"
                    >
                      <v-icon>mdi-palette</v-icon>
                    </v-btn>
                  </template>
                  <v-card>
                    <v-card-text class="pa-0">
                      <v-color-picker
                        :value="item.color"
                        @input="onColorChange(index, $event)"
                        mode="hexa"
                        flat
                      />
                    </v-card-text>
                  </v-card>
                </v-menu>

                <v-menu
                  v-model="item.categoryMenu"
                  top
                  :close-on-content-click="false"
                >
                  <template v-slot:activator="{ on, attrs }">
                    <v-btn
                      v-if="!item.category"
                      icon
                      x-small
                      class="mr-2"
                      v-bind="attrs"
                      v-on="on"
                    >
                      <v-icon>mdi-menu</v-icon>
                    </v-btn>

                    <v-btn
                      v-else
                      x-small
                      :color="item.category.color || item.color"
                      class="mr-2"
                      v-bind="attrs"
                      v-on="on"
                    >
                      {{ item.category.name }}
                    </v-btn>
                  </template>
                  <v-card>
                    <v-card-text>
                      <v-combobox
                        clearable
                        v-model="item.category"
                        :items="annotationCategories"
                        item-text="name"
                        flat
                        @change="onAnnotationCategoryChange(item)"
                      >
                        <template v-slot:item="{ item: catItem }">
                          {{ catItem.name }}
                        </template>
                        <template v-slot:selection="{ item: catItem }">
                          {{ catItem.name }}
                        </template>
                      </v-combobox>
                    </v-card-text>
                  </v-card>
                </v-menu>
                <span>{{ item.name }}</span>
                <v-btn icon class="ml-2" x-small @click="onDeleteItem(index)">
                  <v-icon>mdi-close</v-icon>
                </v-btn>
              </v-chip>
            </template>
          </v-combobox>

          <v-btn class="mr-4" @click="submit" :disabled="isSubmitting">
            {{ $t("timelineSegment.update") }}
          </v-btn>
          <v-btn @click="close">{{ $t("timelineSegment.close") }}</v-btn>
        </v-form>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapStores } from "pinia";
import { useTimelineStore } from "@/store/timeline";
import { useTimelineSegmentStore } from "@/store/timeline_segment";
import { useAnnotationCategoryStore } from "../store/annotation_category";
import { useAnnotationStore } from "../store/annotation";
import { useTimelineSegmentAnnotationStore } from "../store/timeline_segment_annotation";

function getRandomColor() {
  const letters = "0123456789ABCDEF";
  let color = "#";
  for (let i = 0; i < 6; i++) {
    color += letters[Math.floor(Math.random() * 16)];
  }
  return color;
}

function onlySpaces(str) {
  return /^\s*$/.test(str);
}

function uniqueIdArray(list) {
  const map = new Map();
  list.forEach((item) => {
    if (item?.id) {
      map.set(item.id, item);
    }
  });
  return Array.from(map.values());
}

export default {
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    annotateRange: {
      type: Boolean,
      default: false,
    },
    timelineId: {
      type: [String, Number],
      default: null,
    },
  },
  data() {
    return {
      search: null,
      lastKey: null,
      isSubmitting: false,
      annotationsProxy: null,
      annotationCategoriesProxy: null,
    };
  },
  computed: {
    ...mapStores(
      useTimelineStore,
      useTimelineSegmentStore,
      useAnnotationCategoryStore,
      useAnnotationStore,
      useTimelineSegmentAnnotationStore
    ),
    allExistingAnnotationCategories() {
      return this.annotationCategoryStore.all || [];
    },
    annotationCategories: {
      get() {
        return this.annotationCategoriesProxy === null
          ? this.allExistingAnnotationCategories
          : this.annotationCategoriesProxy;
      },
      set(val) {
        this.annotationCategoriesProxy = val;
      },
    },
    allExistingAnnotations() {
      return (this.annotationStore.all || []).map((e) => ({
        ...e,
        color: e.color || "#1976D2",
        colorMenu: false,
        categoryMenu: false,
        category: e.category_id
          ? this.annotationCategoryStore.get(e.category_id)
          : null,
      }));
    },
    timelineSegments() {
      return this.timelineSegmentStore.selected || [];
    },
    currentAnnotations() {
      let segments = [];
      if (this.annotateRange && this.timelineId) {
        const start = this.timelineStore.selectedTimeRangeStart;
        const end = this.timelineStore.selectedTimeRangeEnd;
        segments = this.timelineSegmentStore.forTimelineTimeRange(
          this.timelineId,
          start,
          end
        );
      } else {
        segments = this.timelineSegments;
      }

      const annotations = (segments || []).flatMap((s) => {
        const segmentAnnotations =
          this.timelineSegmentAnnotationStore.forTimelineSegment(s.id) || [];
        return segmentAnnotations.map((a) => {
          const annotation = this.annotationStore.get(a.annotation_id) || {};
          return {
            name: annotation.name,
            color: annotation.color || "#1976D2",
            id: annotation.id,
            colorMenu: false,
            categoryMenu: false,
            category: annotation.category_id
              ? this.annotationCategoryStore.get(annotation.category_id)
              : null,
          };
        });
      });

      return uniqueIdArray(annotations);
    },
    annotations: {
      get() {
        return this.annotationsProxy === null
          ? this.currentAnnotations
          : this.annotationsProxy;
      },
      set(val) {
        this.annotationsProxy = val;
      },
    },
  },
  methods: {
    onDeleteItem(index) {
      const annotations = [...this.annotations];
      annotations.splice(index, 1);
      this.annotationsProxy = annotations;
    },
    onColorChange(index, newColor) {
      console.log(JSON.stringify(newColor));
      const hexColor =
        typeof newColor === "object" && newColor !== null
          ? newColor.hex
          : newColor;

      const updated = this.annotations.map((item, idx) => {
        if (idx === index) {
          return {
            ...item,
            color: hexColor,
          };
        }
        return item;
      });
      console.log(JSON.stringify(updated));
      this.annotationsProxy = updated;
    },
    async onKeydown(event) {
      if (event.code === "Enter" && this.lastKey === "Enter") {
        await this.submit();
      }
      if (event.code === "Enter") {
        event.preventDefault();
      }
      this.lastKey = event.code;
    },
    onAnnotationChange() {
      if (this.isSubmitting) return;

      let inputs = [];

      this.annotations.forEach((e) => {
        if (typeof e === "string") {
          if (onlySpaces(e)) return;

          const splits = e.split(":");
          if (splits.length > 1) {
            const categoryName = splits.shift().trim();
            const name = splits.join(":").trim();

            if (onlySpaces(categoryName) || onlySpaces(name)) return;

            const existingCat = this.annotationCategories.find(
              (cat) => cat.name === categoryName
            );

            if (existingCat) {
              inputs.push({
                name,
                color: existingCat.color || getRandomColor(),
                colorMenu: false,
                categoryMenu: false,
                category: existingCat,
              });
            } else {
              const color = getRandomColor();
              inputs.push({
                name,
                color,
                colorMenu: false,
                categoryMenu: false,
                category: { name: categoryName, color },
              });
            }
          } else {
            inputs.push({
              name: e.trim(),
              color: getRandomColor(),
              colorMenu: false,
              categoryMenu: false,
              category: null,
            });
          }
        } else if (typeof e === "object" && e !== null) {
          inputs.push({
            colorMenu: false,
            categoryMenu: false,
            ...e,
          });
        }
      });

      // Match against pre-existing annotations in the store
      inputs = inputs.map((item) => {
        const found = this.allExistingAnnotations.find((existing) => {
          const matchCat =
            (!item.category && !existing.category) ||
            item.category?.name === existing.category?.name;
          return matchCat && item.name === existing.name;
        });
        return found
          ? {
              ...found,
              colorMenu: item.colorMenu ?? false,
              categoryMenu: item.categoryMenu ?? false,
            }
          : item;
      });

      // Deduplicate selections
      const uniqueMap = new Map();
      inputs.forEach((item) => {
        const key = item.category
          ? `${item.category.name}:${item.name}`
          : item.name;
        if (!uniqueMap.has(key)) {
          uniqueMap.set(key, item);
        } else {
          const current = uniqueMap.get(key);
          if (!current.id && item.id) {
            uniqueMap.set(key, item);
          }
        }
      });

      this.annotationsProxy = Array.from(uniqueMap.values());
    },
    onAnnotationCategoryChange(item) {
      item.categoryMenu = false;
      if (typeof item.category === "string") {
        const newCategory = {
          name: item.category,
          color: item.color,
        };
        this.annotationCategoriesProxy = [
          ...this.annotationCategories,
          newCategory,
        ];
        item.category = newCategory;
      } else if (item.category && item.category.color) {
        item.color = item.category.color;
      }
      this.annotationsProxy = [...this.annotations];
    },
    async submit() {
      console.log(JSON.stringify(this.annotations));
      if (this.isSubmitting) return;
      this.isSubmitting = true;

      try {
        if (this.annotateRange) {
          await this.timelineSegmentStore.annotateRange({
            timelineId: this.timelineId,
            annotations: this.annotations,
          });
        } else {
          await this.timelineSegmentStore.annotateSegments({
            timelineSegmentIds: this.timelineSegments.map((e) => e.id),
            annotations: this.annotations,
          });
        }
        this.$emit("update:show", false);
      } catch (err) {
        console.error("Failed to save annotations:", err);
      } finally {
        this.isSubmitting = false;
      }
    },
    close() {
      this.$emit("update:show", false);
    },
  },
  watch: {
    show(val) {
      if (val) {
        this.search = null;
        this.lastKey = null;
        this.isSubmitting = false;
        this.annotationsProxy = null;
        this.annotationCategoriesProxy = null;
      }
    },
  },
};
</script>
