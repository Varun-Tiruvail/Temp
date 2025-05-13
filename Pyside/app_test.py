import sys
import pytest
from PySide6.QtWidgets import QApplication
from Test import MainWindow

# Initialize QApplication for tests
@pytest.fixture(scope="session")
def app():
    # Only create QApplication once
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # No cleanup needed since QApplication will be cleaned up at program exit

@pytest.fixture
def window(app):
    # Create a fresh window instance for each test
    window = MainWindow()
    yield window
    window.close()

def test_window_title(window):
    """Test if window title is set correctly"""
    assert window.windowTitle() == "MDX Query Builder"

def test_window_geometry(window):
    """Test if window geometry is set correctly"""
    assert window.geometry().x() == 100
    assert window.geometry().y() == 100
    assert window.geometry().width() == 1200
    assert window.geometry().height() == 800

def test_ui_components_exist(window):
    """Test if all major UI components are initialized"""
    assert window.connection_string is not None
    assert window.connect_btn is not None
    assert window.cube_combo is not None
    assert window.metadata_tree is not None
    assert window.columns_list is not None
    assert window.rows_list is not None
    assert window.filters_list is not None
    assert window.query_edit is not None
    assert window.non_empty_cols is not None
    assert window.non_empty_rows is not None
    assert window.export_btn is not None

def test_metadata_tree_header(window):
    """Test if metadata tree header is set correctly"""
    assert window.metadata_tree.headerLabel() == "Cube Structure"

def test_initial_connection_state(window):
    """Test if initial connection is None"""
    assert window.connection is None

def test_checkbox_initial_states(window):
    """Test if checkboxes are initially unchecked"""
    assert not window.non_empty_cols.isChecked()
    assert not window.non_empty_rows.isChecked()

def test_connect_button_text(window):
    """Test if connect button has correct text"""
    assert window.connect_btn.text() == "Connect"

def test_export_button_text(window):
    """Test if export button has correct text"""
    assert window.export_btn.text() == "Export Python Code"

def test_combobox_initial_state(window):
    """Test if cube combo box is initially empty"""
    assert window.cube_combo.count() == 0