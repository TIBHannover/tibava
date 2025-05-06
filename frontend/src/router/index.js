import Vue from 'vue';
import VueRouter from 'vue-router';
import Home from '@/views/Home.vue';
import VideoAnalysis from '@/views/VideoAnalysis.vue';


Vue.use(VueRouter);
const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes: [
    { path: '/', name: 'Home', component: Home },
    { path: '/videoanalysis/:id', name: 'VideoAnalysis', component: VideoAnalysis },
    // { path: '*', name: 'NotFound', component: NotFound },
  ],
});

export default router;
