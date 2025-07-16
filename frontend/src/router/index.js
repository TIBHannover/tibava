import Vue from "vue";
import VueRouter from "vue-router";
import Home from "@/views/Home.vue";
import HomeMenu from "@/views/HomeMenu.vue";
import VideoAnalysis from "@/views/VideoAnalysis.vue";
import VideoAnalysisMenu from "@/views/VideoAnalysisMenu.vue";

Vue.use(VueRouter);
const router = new VueRouter({
  mode: "history",
  base: process.env.BASE_URL,
  routes: [
    { path: "/", name: "Home", components: { default: Home, menu: HomeMenu } },
    {
      path: "/videoanalysis/:id",
      name: "VideoAnalysis",
      components: { default: VideoAnalysis, menu: VideoAnalysisMenu },
    },
    // { path: '*', name: 'NotFound', component: NotFound },
  ],
});

export default router;
