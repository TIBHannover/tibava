<template>
  <v-dialog persistent v-model="show" max-width="1000" @keydown.esc="close">
    <v-card>
      <v-toolbar color="primary" dark>{{
        $t("timelineSegment.title")
      }}</v-toolbar>
      <v-card-text>
        <v-form @submit="submit">
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
                <v-btn disable icon x-small :color="item.color" class="mr-1">
                  <v-icon>{{ "mdi-palette" }}</v-icon>
                </v-btn>
                <v-btn
                  v-if="item.category"
                  disable
                  x-small
                  :color="item.color"
                  class="mr-1"
                  >{{ item.category.name }}
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
                  <template v-slot:activator="{ on }">
                    <v-btn
                      disable
                      icon
                      x-small
                      :color="item.color"
                      class="mr-1"
                      v-on="on"
                    >
                      <v-icon>{{ "mdi-palette" }}</v-icon>
                    </v-btn>
                  </template>
                  <v-card>
                    <v-card-text class="pa-0">
                      <v-color-picker v-model="item.color" flat />
                    </v-card-text>
                  </v-card>
                </v-menu>

                <v-menu
                  v-model="item.categoryMenu"
                  top
                  :close-on-content-click="false"
                >
                  <template v-slot:activator="{ on }">
                    <v-btn
                      v-if="!item.category"
                      disable
                      icon
                      x-small
                      :color="item.category ? item.category.color : ''"
                      class="mr-2"
                      v-on="on"
                    >
                      <v-icon>{{ "mdi-menu" }}</v-icon>
                    </v-btn>

                    <v-btn
                      v-else
                      disable
                      x-small
                      :color="item.color"
                      class="mr-2"
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
                        flat
                        @change="onAnnotationCategoryChange(item)"
                      >
                        <template v-slot:item="{ item }">
                          {{ item.name }}
                        </template>
                        <template v-slot:selection="{ item }">
                          {{ item.name }}
                        </template>
                      </v-combobox>
                    </v-card-text>
                  </v-card>
                </v-menu>
                <span>{{ item.name }}</span>
                <v-btn icon class="ml-2" x-small @click="onDeleteItem(index)">
                  <v-icon>{{ "mdi-close" }}</v-icon>
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
function getRandomColor() {
  var letters = "0123456789ABCDEF";
  var color = "#";
  for (var i = 0; i < 6; i++) {
    color += letters[Math.floor(Math.random() * 16)];
  }
  return color;
}
function onlySpaces(str) {
  return /^\s*$/.test(str);
}

import { mapStores } from "pinia";

import { useTimelineStore } from "@/store/timeline";
import { useTimelineSegmentStore } from "@/store/timeline_segment";
import { useAnnotationCategoryStore } from "../store/annotation_category";
import { useAnnotationStore } from "../store/annotation";
import { useTimelineSegmentAnnotationStore } from "../store/timeline_segment_annotation";

function uniqueIdArray(l) {
  let keys = {};
  l.forEach((e) => {
    keys[e.id] = e;
  });

  return Object.keys(keys).map((v) => keys[v]);
}

export default {
  props: {
    show: {
      default: false,
    },
    annotateRange: {
      default: false,
    },
    timelineId: {
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
    allExistingAnnotationCategories() {
      let annotationCategories = this.annotationCategoryStore.all;

      console.log(
        `annotationCategories ${JSON.stringify(annotationCategories)}`
      );
      return annotationCategories;
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
      let annotations = this.annotationStore.all;
      annotations.map((e) => {
        if ("category_id" in e) {
          e.category = this.annotationCategoryStore.get(e.category_id);
        }
        return e;
      });
      return annotations;
    },
    currentAnnotations() {
      let annotations = [];
      if (this.annotateRange && this.timelineId) {
        const start = this.timelineStore.selectedTimeRangeStart;
        const end = this.timelineStore.selectedTimeRangeEnd;
        const timelineSegments = this.timelineSegmentStore.forTimelineTimeRange(
          this.timelineId,
          start,
          end
        );
        console.log(timelineSegments);
        annotations = timelineSegments
          .map((s) => {
            return this.timelineSegmentAnnotationStore
              .forTimelineSegment(s.id)
              .map((a) => {
                const annotation = this.annotationStore.get(a.annotation_id);
                let category = null;
                if ("category_id" in annotation) {
                  category = this.annotationCategoryStore.get(
                    annotation.category_id
                  );
                }
                return {
                  name: annotation.name,
                  color: annotation.color,
                  id: annotation.id,
                  category: category,
                };
              });
          })
          .flat();
      } else {
        annotations = this.timelineSegments
          .map((s) => {
            return this.timelineSegmentAnnotationStore
              .forTimelineSegment(s.id)
              .map((a) => {
                const annotation = this.annotationStore.get(a.annotation_id);
                let category = null;
                if ("category_id" in annotation) {
                  category = this.annotationCategoryStore.get(
                    annotation.category_id
                  );
                }
                return {
                  name: annotation.name,
                  color: annotation.color,
                  id: annotation.id,
                  category: category,
                };
              });
          })
          .flat();
      }

      annotations = uniqueIdArray(annotations);

      console.log(annotations);
      return annotations;
    },
    annotations: {
      get() {
        return this.annotationsProxy === null
          ? this.currentAnnotations
          : this.annotationsProxy;
      },
      set(val) {
        console.log(`Set value ${JSON.stringify(val)}`);
        this.annotationsProxy = val;
      },
    },
    timelineSegments() {
      return this.timelineSegmentStore.selected;
    },
    ...mapStores(
      useTimelineStore,
      useTimelineSegmentStore,
      useAnnotationCategoryStore,
      useAnnotationStore,
      useTimelineSegmentAnnotationStore
    ),
  },
  methods: {
    onDeleteItem(index) {
      const annotations = [...this.annotations];
      annotations.splice(index, 1);
      this.annotationsProxy = annotations;
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
      if (this.isSubmitting) {
        return;
      }
      let inputs = [];
      let self = this;
      // split string annotations
      this.annotations.forEach((e) => {
        if (typeof e === "string") {
          //filter empty name and categories
          if (onlySpaces(e)) {
            return;
          }
          let splits = e.split(":");
          if (splits.length > 1) {
            let category = splits.shift();
            let name = splits.join(":");
            //filter empty name and categories
            if (onlySpaces(category)) {
              return;
            }
            if (onlySpaces(name)) {
              return;
            }
            let color = getRandomColor();
            // Filter existing categories and use the color of the category
            let existingCategory = self.categories.filter(
              (e) => e.name === category
            );
            if (existingCategory.length > 0) {
              inputs.push({
                name: name,
                color: existingCategory[0].color,
                category: existingCategory[0],
              });
            } else {
              inputs.push({
                name: name,
                color: color,
                category: { name: category, color: color },
              });
            }
          } else {
            inputs.push({
              name: e,
              color: getRandomColor(),
              category: null,
            });
          }
        } else if (typeof e === "object") {
          inputs.push(e);
        }
      });
      //check if the name already exists

      inputs = inputs.map((e) => {
        let existing = this.allExistingAnnotations.find((i) => {
          if (e.category === i.category && e.name === i.name) {
            return true;
          } else if (!e.category && !i.category && e.name === i.name) {
            return true;
          }
          return false;
        });
        if (existing) {
          return existing;
        } else {
          return e;
        }
      });
      //filter all duplicates
      let existing = {};
      inputs.forEach((e, i) => {
        let name = "";
        if (e.category) {
          name = `${e.category.name}:${e.name}`;
        } else {
          name = `${e.name}`;
        }
        if (!(name in existing)) {
          existing[name] = { element: e, index: i };
        } else {
          // if the existing element has already an id we will skipt that
          if ("id" in existing[name]) {
            return;
          }
          if ("id" in e) {
            existing[name] = { element: e, index: i };
            return;
          }
          if ("category" in existing && "category" in e) {
            if ("id" in existing.category) {
              return;
            }

            if ("id" in e.category) {
              existing[name] = { element: e, index: i };
              return;
            }
          }
        }
      });

      if (this.isSubmitting) {
        return;
      }

      inputs = Object.keys(existing).map((e) => {
        return existing[e].element;
      });
      this.annotationsProxy = inputs;
    },
    onAnnotationCategoryChange(item) {
      item.categoryMenu = false;
      if (typeof item.category === "string") {
        console.log(item);
        // categoryNames;

        const annotationCategories = [...this.annotationCategories];
        annotationCategories.push({
          name: item.category,
          color: item.color,
        });
        this.annotationCategoriesProxy = annotationCategories;

        item.category = {
          name: item.category,
          color: item.color,
        };
      }
    },
    async submit() {
      if (this.isSubmitting) {
        return;
      }
      this.isSubmitting = true;

      if (this.annotateRange) {
        await this.timelineSegmentStore.annotateRange({
          timelineId: this.timelineId,
          annotations: this.annotations,
        });
      } else {
        console.log(this.timelineSegments.map((e) => e.id));
        await this.timelineSegmentStore.annotateSegments({
          timelineSegmentIds: this.timelineSegments.map((e) => e.id),
          annotations: this.annotations,
        });
      }

      // TODO

      this.isSubmitting = false;
      this.$emit("update:show", false);
    },
    close() {
      this.$emit("update:show", false);
    },
  },
  watch: {
    show(newValue) {
      if (newValue) {
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
