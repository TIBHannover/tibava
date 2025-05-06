from django.contrib import admin
from django.urls import path

from . import views

urlpatterns = [
    path("user/csrf", views.get_csrf_token, name="get_csrf_token"),
    path("user/login", views.login, name="login"),
    path("user/logout", views.logout, name="logout"),
    path("user/register", views.register, name="register"),
    path("user/get", views.UserGet.as_view(), name="user_get"),
    #
    path("video/upload", views.VideoUpload.as_view(), name="video_upload"),
    path("video/list", views.VideoList.as_view(), name="video_list"),
    path("video/get", views.VideoGet.as_view(), name="video_get"),
    path("video/rename", views.VideoRename.as_view(), name="video_rename"),
    path("video/delete", views.VideoDelete.as_view(), name="video_delete"),
    #
    path("video/export", views.VideoExport.as_view(), name="video_export"),
    #
    path("plugin/list", views.PluginList.as_view(), name="plugin_list"),
    path("plugin/run/new", views.PluginRunNew.as_view(), name="plugin_run_new"),
    path("plugin/run/list", views.PluginRunList.as_view(), name="plugin_run_list"),
    path(
        "plugin/run/delete", views.PluginRunDelete.as_view(), name="plugin_run_delete"
    ),
    path(
        "plugin/run/result/list",
        views.PluginRunResultList.as_view(),
        name="plugin_run_list",
    ),
    #
    path(
        "cluster/timeline/item/create",
        views.ClusterTimelineItemCreate.as_view(),
        name="cluster_timeline_item_create",
    ),
    path(
        "cluster/timeline/item/fetch",
        views.ClusterTimelineItemFetch.as_view(),
        name="cluster_timeline_item_fetch",
    ),
    path(
        "cluster/timeline/item/rename",
        views.ClusterTimelineItemRename.as_view(),
        name="cluster_timeline_item_rename",
    ),
    path(
        "cluster/timeline/item/delete",
        views.ClusterTimelineItemDelete.as_view(),
        name="cluster_timeline_item_delete",
    ),
    path("cluster/timeline/item/merge", views.ClusterTimelineItemMerge.as_view()),
    #
    path(
        "cluster/item/fetch",
        views.ClusterItemFetch.as_view(),
        name="cluster_item_fetch",
    ),
    path(
        "cluster/item/delete",
        views.ClusterItemDelete.as_view(),
        name="cluster_item_delete",
    ),
    path("cluster/item/move", views.ClusterItemMove.as_view()),
    #
    path("timeline/list", views.TimelineList.as_view(), name="timeline_list"),
    path("timeline/list_all", views.TimelineListAll.as_view()),
    path(
        "timeline/duplicate",
        views.TimelineDuplicate.as_view(),
        name="timeline_duplicate",
    ),
    path("timeline/rename", views.TimelineRename.as_view(), name="timeline_rename"),
    path(
        "timeline/setparent",
        views.TimelineSetParent.as_view(),
        name="timeline_setparent",
    ),
    path(
        "timeline/setcollapse",
        views.TimelineSetCollapse.as_view(),
        name="timeline_setcollapse",
    ),
    path(
        "timeline/setorder", views.TimelineSetOrder.as_view(), name="timeline_setorder"
    ),
    path(
        "timeline/changevisualization",
        views.TimelineChangeVisualization.as_view(),
        name="timeline_change_visualization",
    ),
    path(
        "timeline/import/eaf",
        views.TimelineImportEAF.as_view(),
        name="timeline_import_eaf",
    ),
    path("timeline/delete", views.TimelineDelete.as_view(), name="timeline_delete"),
    path("timeline/create", views.TimelineCreate.as_view(), name="timeline_create"),
    #
    path(
        "timeline/segment/get",
        views.TimelineSegmentGet.as_view(),
        name="timeline_segment_get",
    ),
    path(
        "timeline/segment/list",
        views.TimelineSegmentList.as_view(),
        name="timeline_segment_list",
    ),
    path(
        "timeline/segment/merge",
        views.TimelineSegmentMerge.as_view(),
        name="timeline_segment_list",
    ),
    path(
        "timeline/segment/split",
        views.TimelineSegmentSplit.as_view(),
        name="timeline_segment_list",
    ),
    path(
        "timeline/segment/annotate",
        views.TimelineSegmentAnnotate.as_view(),
        name="timeline_segment_annotate",
    ),
    path(
        "timeline/segment/annotate/range",
        views.TimelineSegmentAnnotateRange.as_view(),
        name="timeline_segment_annotate_range",
    ),
    #
    path(
        "timeline/segment/annotation/list",
        views.TimelineSegmentAnnoatationList.as_view(),
        name="timeline_segment_annotation_list",
    ),
    path(
        "timeline/segment/annotation/create",
        views.TimelineSegmentAnnoatationCreate.as_view(),
        name="timeline_segment_annotation_create",
    ),
    path(
        "timeline/segment/annotation/toggle",
        views.TimelineSegmentAnnoatationToggle.as_view(),
        name="timeline_segment_annotation_toggle",
    ),
    path(
        "timeline/segment/annotation/delete",
        views.TimelineSegmentAnnoatationDelete.as_view(),
        name="timeline_segment_annotation_delete",
    ),
    #
    path(
        "annotation/category/list",
        views.AnnoatationCategoryList.as_view(),
        name="annotation_category_list",
    ),
    path(
        "annotation/category/create",
        views.AnnoatationCategoryCreate.as_view(),
        name="annotation_category_create",
    ),
    path(
        "annotation/category/update",
        views.AnnoatationCategoryCreate.as_view(),
        name="annotation_category_create",
    ),
    path(
        "annotation/category/delete",
        views.AnnoatationCategoryCreate.as_view(),
        name="annotation_category_create",
    ),
    #
    path("annotation/list", views.AnnoatationList.as_view(), name="annotation_list"),
    path(
        "annotation/create", views.AnnoatationCreate.as_view(), name="annotation_create"
    ),
    path(
        "annotation/update", views.AnnoatationChange.as_view(), name="annotation_change"
    ),
    path(
        "annotation/delete", views.AnnoatationChange.as_view(), name="annotation_change"
    ),
    #
    path("shortcut/list", views.ShortcutList.as_view(), name="shortcut_list"),
    path("shortcut/create", views.ShortcutCreate.as_view(), name="shortcut_create"),
    #
    path(
        "annotation/shortcut/list",
        views.AnnotationShortcutList.as_view(),
        name="annotation_shortcut_list",
    ),
    path(
        "annotation/shortcut/create",
        views.AnnotationShortcutCreate.as_view(),
        name="annotation_shortcut_create",
    ),
    path(
        "annotation/shortcut/update",
        views.AnnotationShortcutUpdate.as_view(),
        name="annotation_shortcut_update",
    ),
    path(
        "video/analysis/get",
        views.VideoAnalysisStateGet.as_view(),
        name="video_analysis_get",
    ),
    path(
        "video/analysis/setselectedshots",
        views.VideoAnalysisStateSetSelectedShots.as_view(),
        name="video_analysis_set_selected_shots",
    ),
    path(
        "video/analysis/setselectedplaceclustering",
        views.VideoAnalysisStateSetSelectedPlaceClustering.as_view(),
        name="video_analysis_set_selected_place_clustering",
    ),
    path(
        "video/analysis/setselectedfaceclustering",
        views.VideoAnalysisStateSetSelectedFaceClustering.as_view(),
        name="video_analysis_set_selected_face_clustering",
    ),
]
