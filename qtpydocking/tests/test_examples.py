import pytest
from qtpy import QtGui, QtCore, QtWidgets

import qtpydocking
from qtpydocking import examples, DockWidgetArea


@pytest.fixture(scope='function',
                params=['simple', 'demo']
                )
def example(qtbot, qapp, request):
    example_module = getattr(examples, request.param)
    main = example_module.main(qapp)
    qtbot.addWidget(main)
    yield main


@pytest.fixture(scope='function')
def manager(example):
    return example.dock_manager


@pytest.fixture(scope='function')
def containers(manager):
    return manager.dock_containers()


def test_smoke_example(qtbot, manager: qtpydocking.DockManager):
    # DockManager
    manager.container_overlay()
    manager.dock_area_overlay()
    manager.set_config_flags(manager.config_flags())
    manager.find_dock_widget('')
    manager.dock_widgets_map()
    manager.dock_containers()
    manager.floating_widgets()
    manager.floating_widgets()
    manager.restore_state(manager.save_state())
    manager.add_perspective('test')
    assert manager.perspective_names() == ['test']
    settings = QtCore.QSettings()
    manager.save_perspectives(settings)
    manager.remove_perspectives('test')
    manager.load_perspectives(settings)
    manager.view_menu()
    manager.open_perspective('test')
    manager.set_view_menu_insertion_order(qtpydocking.InsertionOrder.by_spelling)

    # DockContainerWidget
    manager.create_root_splitter()
    manager.root_splitter()
    manager.last_added_dock_area_widget(DockWidgetArea.left)
    manager.has_top_level_dock_widget()
    manager.top_level_dock_widget()
    manager.top_level_dock_area()
    manager.dock_widgets()
    assert not manager.is_in_front_of(manager)
    manager.dock_area_at(QtCore.QPoint(0, 0))
    manager.dock_area(0)
    assert manager.dock_area(999) is None
    manager.opened_dock_areas()
    manager.dock_area_count()
    manager.visible_dock_area_count()
    manager.dump_layout()
    manager.features()
    manager.floating_widget()
    manager.close_other_areas(DockWidgetArea.top)


def test_smoke_example_adding(qtbot, manager: qtpydocking.DockManager):
    for area in (DockWidgetArea.left,
                 DockWidgetArea.right,
                 DockWidgetArea.top,
                 DockWidgetArea.bottom,
                 ):
        widget = qtpydocking.DockWidget('test')
        widget.set_widget(QtWidgets.QLabel('test'))
        manager.add_dock_widget_tab(area, widget)

    widget = qtpydocking.DockWidget('test')
    qtbot.addWidget(widget)
    widget.set_widget(QtWidgets.QLabel('test'))
    manager.add_dock_widget_tab_to_area(widget, manager.top_level_dock_area())


def test_smoke_example_add_floating(qtbot, manager: qtpydocking.DockManager):
    widget = qtpydocking.DockWidget('test')
    qtbot.addWidget(widget)
    widget.set_widget(QtWidgets.QLabel('test'))

    # tests: manager.add_dock_area() with dock_widget set
    floating = qtpydocking.FloatingDockContainer(
        dock_widget=widget, dock_manager=manager)


def test_smoke_example_add_floating_container(qtbot, manager: qtpydocking.DockManager):
    widget = qtpydocking.DockWidget('test')
    qtbot.addWidget(widget)
    widget.set_widget(QtWidgets.QLabel('test'))

    area = manager.opened_dock_areas()[0]
    floating = qtpydocking.FloatingDockContainer(
        dock_widget=widget, dock_area=area)

    for area in manager.opened_dock_areas():
        manager.remove_dock_area(area)


def test_smoke_make_area_floating(example):
    for container in example.dock_manager.dock_containers():
        print('container', container.z_order_index())
        floating_widget = container.floating_widget()


# def test_container_saving(containers):
#     for container in containers:
#         container.top_level_dock_widget()
#         container.restore_state(container.save_state())
#         assert floating.dock_container() is container
#         floating.is_closable()
#         floating.has_top_level_dock_widget()
#         floating.top_level_dock_widget()
#         floating.dock_widgets()


def test_smoke_widget(qtbot, manager: qtpydocking.DockManager):
    widget = qtpydocking.DockWidget('test')
    qtbot.addWidget(widget)

    label = QtWidgets.QLabel('test')
    widget.set_widget(label)
    assert widget.widget() is label

    widget.create_default_tool_bar()
    assert widget.tool_bar()
    widget.set_toolbar_floating_style(False)
    widget.set_toolbar_floating_style(True)

    tool_bar = QtWidgets.QToolBar()
    widget.set_tool_bar(tool_bar)
    widget.set_tool_bar_style(QtCore.Qt.ToolButtonTextUnderIcon,
                              state=qtpydocking.WidgetState.floating)
    assert widget.tool_bar_style(qtpydocking.WidgetState.floating) == QtCore.Qt.ToolButtonTextUnderIcon

    widget.set_tool_bar_style(QtCore.Qt.ToolButtonIconOnly,
                              state=qtpydocking.WidgetState.hidden)
    assert widget.tool_bar_style(qtpydocking.WidgetState.hidden) == QtCore.Qt.ToolButtonIconOnly

    widget.set_tool_bar_icon_size(QtCore.QSize(25, 25),
                                  state=qtpydocking.WidgetState.floating)
    assert widget.tool_bar_icon_size(qtpydocking.WidgetState.floating) == QtCore.QSize(25, 25)
    widget.set_tool_bar_icon_size(QtCore.QSize(26, 26),
                                  state=qtpydocking.WidgetState.hidden)
    assert widget.tool_bar_icon_size(qtpydocking.WidgetState.hidden) == QtCore.QSize(26, 26)

    widget.set_tab_tool_tip('tooltip')
    widget.toggle_view(True)
    widget.toggle_view(False)

    widget.set_feature(widget.features(), on=True)
    widget.set_features(widget.features())

    widget.set_dock_manager(manager)
    assert widget.dock_manager() is manager

    widget.flag_as_unassigned()


def test_smoke_floating(qtbot, manager: qtpydocking.DockManager):
    widget = qtpydocking.DockWidget('test')
    qtbot.addWidget(widget)

    widget.set_widget(QtWidgets.QLabel('test'))
    floating = qtpydocking.FloatingDockContainer(
        dock_widget=widget, dock_manager=manager)

    floating.on_dock_areas_added_or_removed()
    floating.on_dock_area_current_changed(0)
    floating.init_floating_geometry(QtCore.QPoint(0, 0), QtCore.QSize(100,
                                                                      100))
    floating.start_floating(QtCore.QPoint(0, 0), QtCore.QSize(100, 100),
                            qtpydocking.DragState.inactive)

    floating.start_dragging(QtCore.QPoint(10, 0), QtCore.QSize(100, 100))

    floating.update_window_title()

    widget.set_feature(qtpydocking.DockWidgetFeature.closable, False)
    floating.close()

    widget.set_feature(qtpydocking.DockWidgetFeature.closable, True)
    floating.close()

    floating.dock_container()
    floating.has_top_level_dock_widget()
    floating.top_level_dock_widget()
    floating.dock_widgets()

    floating.deleteLater()


def test_smoke_xml_settings(qtbot, manager: qtpydocking.DockManager):
    manager.set_config_flags(qtpydocking.DockFlags.xml_compression)
    manager.restore_state(manager.save_state())

    manager.set_config_flags(qtpydocking.DockFlags.xml_auto_formatting)
    manager.restore_state(manager.save_state())
