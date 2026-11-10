from django.urls import path

from .views import (
    EquipmentCategoryListCreateView,
    EquipmentCategoryDetailView,
    EquipmentListCreateView,
    EquipmentDetailView,
    MaterialCategoryListCreateView,
    MaterialCategoryDetailView,
    MaterialListCreateView,
    MaterialDetailView,
    StockMovementListCreateView,
    EquipmentUnitListCreateView,
    EquipmentUnitDetailView,
)

urlpatterns = [

    # Equipment categories
    path(
        "equipment-categories/",
        EquipmentCategoryListCreateView.as_view()
    ),
    path(
        "equipment-categories/<int:pk>/",
        EquipmentCategoryDetailView.as_view()
    ),

    # Equipment
    path("equipment/", EquipmentListCreateView.as_view()),
    path("equipment/<int:pk>/", EquipmentDetailView.as_view()),
    path("equipment-units/", EquipmentUnitListCreateView.as_view()),
    path("equipment-units/<int:pk>/", EquipmentUnitDetailView.as_view()),

    # Material categories
    path("material-categories/",MaterialCategoryListCreateView.as_view()),
    path("material-categories/<int:pk>/",MaterialCategoryDetailView.as_view()),

    # Materials
    path("materials/", MaterialListCreateView.as_view()),
    path("materials/<int:pk>/", MaterialDetailView.as_view()),

    # Stock movements
    path("stock-movements/", StockMovementListCreateView.as_view()),
]