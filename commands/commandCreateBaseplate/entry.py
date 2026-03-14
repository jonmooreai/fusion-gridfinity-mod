import adsk.core, adsk.fusion, traceback
import math
import os

from ...lib import configUtils
from ...lib import fusion360utils as futil
from ... import config
from ...lib.gridfinityUtils.const import DIMENSION_DEFAULT_WIDTH_UNIT
from ...lib.gridfinityUtils.baseplateGenerator import createGridfinityBaseplate
from ...lib.gridfinityUtils.baseplateGeneratorInput import BaseplateGeneratorInput
from ...lib.gridfinityUtils import commonUtils
from ...lib.gridfinityUtils import const
from ...lib.gridfinityUtils import drawerGridUtils
from .inputState import InputState
from ...lib.ui.commandUiState import CommandUiState
from ...lib.ui.unsupportedDesignTypeException import UnsupportedDesignTypeException

app = adsk.core.Application.get()
ui = app.userInterface


# The command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdBaseplate'
CMD_NAME = 'Gridfinity baseplate'
CMD_Description = 'Create gridfinity baseplate'

uiState = CommandUiState(CMD_NAME)
# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidCreatePanel'
COMMAND_BESIDE_ID = 'ScriptsManagerCommand'

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

CONFIG_FOLDER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'commandConfig')
UI_INPUT_DEFAULTS_CONFIG_PATH = os.path.join(CONFIG_FOLDER_PATH, "ui_input_defaults.json")

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

# Input groups
INFO_GROUP = 'info_group'
BASIC_SIZES_GROUP = 'basic_sizes'
XY_DIMENSIONS_GROUP = 'xy_dimensions'
PLATE_FEATURES_GROUP = 'plate_features'
MAGNET_SOCKET_GROUP = 'magnet_cutout_group'
SCREW_HOLE_GROUP = 'screw_hole_group'
SIDE_PADDING_GROUP = 'side_padding_group'
ADVANCED_PLATE_SIZE_GROUP = 'advanced_plate_size_group'
INPUT_CHANGES_GROUP = 'input_changes_group'
PREVIEW_GROUP = 'preview_group'
EXPORT_GROUP = 'export_group'
# Input ids
BASEPLATE_BASE_UNIT_WIDTH_INPUT = 'base_width_unit'
BASEPLATE_BASE_UNIT_LENGTH_INPUT = 'base_length_unit'
BIN_XY_CLEARANCE_INPUT_ID = 'bin_xy_clearance'
SPECIFY_BY_MODE_INPUT = 'specify_by_mode'
BASEPLATE_WIDTH_INPUT = 'plate_width'
BASEPLATE_LENGTH_INPUT = 'plate_length'
DRAWER_WIDTH_INPUT = 'drawer_width'
DRAWER_LENGTH_INPUT = 'drawer_length'
DRAWER_DIMENSIONS_UNIT_INPUT = 'drawer_dimensions_unit'
PRINT_PLATE_WIDTH_INPUT = 'print_plate_width'
PRINT_PLATE_LENGTH_INPUT = 'print_plate_length'
PRINT_PLATE_DIMENSIONS_UNIT_INPUT = 'print_plate_dimensions_unit'
BASEPLATE_TYPE_DROPDOWN = 'plate_type_dropdown'

SPECIFY_BY_UNITS = 'Units (u)'
SPECIFY_BY_DRAWER = 'Drawer size'
SPECIFY_BY_PRINT_PLATE = 'Print plate'

DRAWER_UNIT_INCHES = 'Inches'
DRAWER_UNIT_MM = 'mm'

BASEPLATE_TYPE_LIGHT = 'Light'
BASEPLATE_TYPE_FULL = 'Full'
BASEPLATE_TYPE_SKELETONIZED = 'Skeletonized'

BASEPLATE_WITH_MAGNETS_INPUT = 'with_magnet_cutouts'
BASEPLATE_MAGNET_DIAMETER_INPUT = 'magnet_diameter'
BASEPLATE_MAGNET_HEIGHT_INPUT = 'magnet_height'

BASEPLATE_WITH_SCREWS_INPUT = 'with_screw_holes'
BASEPLATE_SCREW_DIAMETER_INPUT = 'screw_diameter'
BASEPLATE_SCREW_HEIGHT_INPUT = 'screw_head_diameter'

BASEPLATE_WITH_SIDE_PADDING_INPUT = 'with_side_padding'
BASEPLATE_SIDE_PADDING_LEFT_INPUT = 'side_padding_left'
BASEPLATE_SIDE_PADDING_TOP_INPUT = 'side_padding_top'
BASEPLATE_SIDE_PADDING_RIGHT_INPUT = 'side_padding_right'
BASEPLATE_SIDE_PADDING_BOTTOM_INPUT = 'side_padding_bottom'

BASEPLATE_EXTRA_THICKNESS_INPUT = 'extra_bottom_thickness'
BASEPLATE_BIN_Z_CLEARANCE_INPUT = 'bin_z_clearance'
BASEPLATE_HAS_CONNECTION_HOLE_INPUT = 'has_connection_hole'
BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT = 'connection_hole_diameter'

INPUT_CHANGES_SAVE_DEFAULTS = 'input_changes_buttons_save_new_defaults'
INPUT_CHANGES_RESET_TO_DEFAULTS = 'input_changes_button_reset_to_defaults'
INPUT_CHANGES_RESET_TO_FACTORY = 'input_changes_button_factory_reset'

SHOW_PREVIEW_INPUT = 'show_preview'
EXPORT_STL_INPUT = 'export_stl_button'
EXPORT_INFO_INPUT = 'export_info_text'

INFO_TEXT = ("<b>Help:</b> Info for inputs can be found "
             "<a href=\"https://github.com/Le0Michine/FusionGridfinityGenerator/wiki/Baseplate-generator-options\">"
             "Here on our GitHub</a>.")

INPUTS_VALID = True
LAST_EXPORT_DIRECTORY = os.path.expanduser('~')
MULTI_PLATE_APPEARANCE_CANDIDATES = [
    ('Red', ['Paint - Enamel Glossy (Red)', 'red']),
    ('Orange', ['Paint - Enamel Glossy (Orange)', 'orange']),
    ('Yellow', ['Paint - Enamel Glossy (Yellow)', 'yellow']),
    ('Green', ['Paint - Enamel Glossy (Green)', 'green']),
    ('Blue', ['Paint - Enamel Glossy (Blue)', 'blue']),
    ('Purple', ['Paint - Enamel Glossy (Purple)', 'purple']),
]


def _get_print_plate_cm():
    """Return (print_width_cm, print_length_cm) from UI, or (0, 0) if not available."""
    try:
        raw_w = uiState.getState(PRINT_PLATE_WIDTH_INPUT)
        raw_l = uiState.getState(PRINT_PLATE_LENGTH_INPUT)
        unit = uiState.getState(PRINT_PLATE_DIMENSIONS_UNIT_INPUT) if uiState.inputState.get(PRINT_PLATE_DIMENSIONS_UNIT_INPUT) else DRAWER_UNIT_MM
        return (_length_to_cm(raw_w, unit), _length_to_cm(raw_l, unit))
    except (KeyError, TypeError):
        return (0.0, 0.0)


def _get_or_create_design_appearance(design: adsk.fusion.Design, label: str, candidates: list[str]):
    """Copy a stock Fusion appearance into the design once, then reuse it."""
    design_name = f'GridfinityGeneratorMod - {label}'
    existing = design.appearances.itemByName(design_name)
    if existing:
        return existing

    for library in app.materialLibraries:
        try:
            for candidate in candidates:
                match = library.appearances.itemByName(candidate)
                if match:
                    return design.appearances.addByCopy(match, design_name)
        except Exception:
            pass

    lowered_candidates = [candidate.lower() for candidate in candidates]
    for library in app.materialLibraries:
        try:
            for index in range(library.appearances.count):
                appearance = library.appearances.item(index)
                appearance_name = appearance.name.lower()
                if any(candidate in appearance_name for candidate in lowered_candidates):
                    return design.appearances.addByCopy(appearance, design_name)
        except Exception:
            pass

    return None


def _apply_multi_plate_appearances(design: adsk.fusion.Design, bodies: list[adsk.fusion.BRepBody]):
    """Color split plates differently so separate printed parts are obvious."""
    palette = []
    for label, candidates in MULTI_PLATE_APPEARANCE_CANDIDATES:
        appearance = _get_or_create_design_appearance(design, label, candidates)
        if appearance:
            palette.append(appearance)

    if not palette:
        return

    for index, body in enumerate(bodies):
        body.appearance = palette[index % len(palette)]


def _sanitize_file_name(value: str) -> str:
    sanitized = ''.join(char if char.isalnum() or char in ('-', '_') else '-' for char in value.strip().lower())
    sanitized = '-'.join(part for part in sanitized.split('-') if part)
    return sanitized or 'gridfinity-baseplate'


def _build_baseplate():
    inputsState = getInputsState()
    des = adsk.fusion.Design.cast(app.activeProduct)
    if des.designType == 0:
        raise UnsupportedDesignTypeException('Timeline must be enabled for the generator to work, projects with disabled design history currently are not supported')

    root = adsk.fusion.Component.cast(des.rootComponent)
    baseplateName = 'Gridfinity baseplate {}x{}'.format(int(inputsState.plateLength), int(inputsState.plateWidth))
    originalTimelineCount = des.timeline.count

    if des.designIntent == adsk.fusion.DesignIntentTypes.HybridDesignIntentType:
        newCmpOcc = adsk.fusion.Occurrences.cast(root.occurrences).addNewComponent(adsk.core.Matrix3D.create())
        newCmpOcc.component.name = baseplateName
        newCmpOcc.activate()
        gridfinityBaseplateComponent: adsk.fusion.Component = newCmpOcc.component
    else:
        gridfinityBaseplateComponent = des.rootComponent

    existingBodyTokens = set()
    for body in gridfinityBaseplateComponent.bRepBodies:
        existingBodyTokens.add(body.entityToken)

    print_w_cm, print_l_cm = _get_print_plate_cm()
    total_w_u = int(inputsState.plateWidth)
    total_l_u = int(inputsState.plateLength)
    num_x, num_y, chunk_widths, chunk_lengths = drawerGridUtils.compute_plate_split(
        total_w_u, total_l_u, print_w_cm, print_l_cm,
        inputsState.baseWidth, inputsState.baseLength, inputsState.xyClearance,
    )
    num_plates = num_x * num_y

    fullInput = BaseplateGeneratorInput()
    fullInput.baseWidth = inputsState.baseWidth
    fullInput.baseLength = inputsState.baseLength
    fullInput.xyClearance = inputsState.xyClearance
    fullInput.baseplateWidth = inputsState.plateWidth
    fullInput.baseplateLength = inputsState.plateLength
    fullInput.hasExtendedBottom = not inputsState.plateType == BASEPLATE_TYPE_LIGHT
    fullInput.hasSkeletonizedBottom = inputsState.plateType == BASEPLATE_TYPE_SKELETONIZED
    fullInput.hasMagnetCutouts = inputsState.hasMagnetSockets
    fullInput.magnetCutoutsDiameter = inputsState.magnetSocketSize
    fullInput.magnetCutoutsDepth = inputsState.magnetSocketDepth
    fullInput.hasScrewHoles = inputsState.hasScrewHoles
    fullInput.screwHolesDiameter = inputsState.screwHoleSize
    fullInput.screwHeadCutoutDiameter = inputsState.screwHeadSize
    fullInput.hasPadding = inputsState.hasPadding
    fullInput.paddingLeft = inputsState.paddingLeft
    fullInput.paddingRight = inputsState.paddingRight
    fullInput.paddingTop = inputsState.paddingTop
    fullInput.paddingBottom = inputsState.paddingBottom
    fullInput.bottomExtensionHeight = inputsState.extraBottomThickness
    fullInput.binZClearance = inputsState.verticalClearance
    fullInput.hasConnectionHoles = inputsState.hasConnectionHoles
    fullInput.connectionScrewHolesDiameter = inputsState.connectionHoleSize
    fullInput.cornerFilletRadius = const.BIN_CORNER_FILLET_RADIUS

    baseplateBody = createGridfinityBaseplate(fullInput, gridfinityBaseplateComponent)
    baseplateBody.name = baseplateName

    if num_plates > 1:
        splitFeatures = gridfinityBaseplateComponent.features.splitBodyFeatures
        generatedBodies = [body for body in gridfinityBaseplateComponent.bRepBodies if body.entityToken not in existingBodyTokens]

        cumulative_width_u = 0
        for chunk_width in chunk_widths[:-1]:
            cumulative_width_u += chunk_width
            split_x = cumulative_width_u * inputsState.baseWidth - 2 * inputsState.xyClearance
            planeInput = gridfinityBaseplateComponent.constructionPlanes.createInput()
            planeInput.setByOffset(
                gridfinityBaseplateComponent.yZConstructionPlane,
                adsk.core.ValueInput.createByReal(split_x),
            )
            splitPlane = gridfinityBaseplateComponent.constructionPlanes.add(planeInput)
            splitPlane.isLightBulbOn = False
            splitInput = splitFeatures.createInput(
                commonUtils.objectCollectionFromList(generatedBodies),
                splitPlane,
                True,
            )
            splitFeatures.add(splitInput)
            generatedBodies = [body for body in gridfinityBaseplateComponent.bRepBodies if body.entityToken not in existingBodyTokens]

        cumulative_length_u = 0
        for chunk_length in chunk_lengths[:-1]:
            cumulative_length_u += chunk_length
            split_y = cumulative_length_u * inputsState.baseLength - 2 * inputsState.xyClearance
            planeInput = gridfinityBaseplateComponent.constructionPlanes.createInput()
            planeInput.setByOffset(
                gridfinityBaseplateComponent.xZConstructionPlane,
                adsk.core.ValueInput.createByReal(split_y),
            )
            splitPlane = gridfinityBaseplateComponent.constructionPlanes.add(planeInput)
            splitPlane.isLightBulbOn = False
            splitInput = splitFeatures.createInput(
                commonUtils.objectCollectionFromList(generatedBodies),
                splitPlane,
                True,
            )
            splitFeatures.add(splitInput)
            generatedBodies = [body for body in gridfinityBaseplateComponent.bRepBodies if body.entityToken not in existingBodyTokens]

    finalBodies = [body for body in gridfinityBaseplateComponent.bRepBodies if body.entityToken not in existingBodyTokens]
    moveFeatures = gridfinityBaseplateComponent.features.moveFeatures
    moveBodies = commonUtils.objectCollectionFromList(finalBodies)

    rotateInput = moveFeatures.createInput2(moveBodies)
    rotateTransform = adsk.core.Matrix3D.create()
    rotateTransform.setToRotation(
        math.radians(90),
        adsk.core.Vector3D.create(1, 0, 0),
        adsk.core.Point3D.create(0, 0, 0),
    )
    rotateInput.defineAsFreeMove(rotateTransform)
    moveFeatures.add(rotateInput)

    flipInput = moveFeatures.createInput2(moveBodies)
    flipTransform = adsk.core.Matrix3D.create()
    flipTransform.setToRotation(
        math.radians(180),
        adsk.core.Vector3D.create(1, 0, 0),
        adsk.core.Point3D.create(0, 0, 0),
    )
    flipInput.defineAsFreeMove(flipTransform)
    moveFeatures.add(flipInput)

    min_x = min(body.boundingBox.minPoint.x for body in finalBodies)
    min_z = min(body.boundingBox.minPoint.z for body in finalBodies)
    if min_x != 0 or min_z != 0:
        translateInput = moveFeatures.createInput2(moveBodies)
        translateTransform = adsk.core.Matrix3D.create()
        translateTransform.translation = adsk.core.Vector3D.create(-min_x, 0, -min_z)
        translateInput.defineAsFreeMove(translateTransform)
        moveFeatures.add(translateInput)

    sortedBodies = list(finalBodies)
    if num_plates > 1:
        sortedBodies = sorted(
            finalBodies,
            key=lambda body: (
                round(body.boundingBox.minPoint.z, 6),
                round(body.boundingBox.minPoint.x, 6),
            ),
        )
        for index, body in enumerate(sortedBodies, start=1):
            body.name = '{} - Plate {} of {}'.format(baseplateName, index, num_plates)
        _apply_multi_plate_appearances(des, sortedBodies)

    return {
        'design': des,
        'component': gridfinityBaseplateComponent,
        'bodies': sortedBodies,
        'name': baseplateName,
        'num_plates': num_plates,
        'timeline_start': originalTimelineCount,
    }


def _export_baseplate_stls():
    global LAST_EXPORT_DIRECTORY

    folderDialog = ui.createFolderDialog()
    folderDialog.title = 'Choose STL export folder'
    folderDialog.initialDirectory = LAST_EXPORT_DIRECTORY
    if folderDialog.showDialog() != adsk.core.DialogResults.DialogOK:
        return False

    exportFolder = folderDialog.folder
    LAST_EXPORT_DIRECTORY = exportFolder

    buildResult = _build_baseplate()
    design = buildResult['design']
    if design.designType == adsk.fusion.DesignTypes.ParametricDesignType:
        plateGroup = design.timeline.timelineGroups.add(buildResult['timeline_start'], design.timeline.count - 1)
        plateGroup.name = buildResult['name']
    exportManager = design.exportManager
    baseFileName = _sanitize_file_name(buildResult['name'])
    num_bodies = len(buildResult['bodies'])

    for index, body in enumerate(buildResult['bodies'], start=1):
        fileStem = '{}-plate-{:02d}-of-{:02d}'.format(baseFileName, index, num_bodies)
        exportPath = os.path.join(exportFolder, fileStem)
        stlOptions = exportManager.createSTLExportOptions(body, exportPath)
        stlOptions.sendToPrintUtility = False
        exportManager.execute(stlOptions)

    ui.messageBox(
        'Exported {} STL file(s) to:\n{}'.format(num_bodies, exportFolder),
        'GridfinityGeneratorMod Export'
    )
    return True


# Conversion to cm. Drawer/print inputs are unitless (raw number in user's chosen unit); this converts to cm for the helper.
def _length_to_cm(value: float, unit: str) -> float:
    """Convert a length value to cm. unit is DRAWER_UNIT_INCHES or DRAWER_UNIT_MM."""
    if unit == DRAWER_UNIT_INCHES:
        return value * 2.54
    return value / 10.0  # mm to cm


def _update_main_dimensions_visibility(inputs, specify_by_mode):
    """Show/hide Plate width-length (u) vs Drawer width-length based on Specify by mode."""
    try:
        # Use registered command inputs so we have valid refs (nested group children may not be found via inputs.itemById)
        baseplateWidthInput = uiState.commandInputs.get(BASEPLATE_WIDTH_INPUT)
        baseplateLengthInput = uiState.commandInputs.get(BASEPLATE_LENGTH_INPUT)
        drawerWidthInput = uiState.commandInputs.get(DRAWER_WIDTH_INPUT)
        drawerLengthInput = uiState.commandInputs.get(DRAWER_LENGTH_INPUT)
        if baseplateWidthInput:
            baseplateWidthInput.isVisible = specify_by_mode == SPECIFY_BY_UNITS
        if baseplateLengthInput:
            baseplateLengthInput.isVisible = specify_by_mode == SPECIFY_BY_UNITS
        if drawerWidthInput:
            drawerWidthInput.isVisible = specify_by_mode == SPECIFY_BY_DRAWER
        if drawerLengthInput:
            drawerLengthInput.isVisible = specify_by_mode == SPECIFY_BY_DRAWER
        drawerUnitInput = uiState.commandInputs.get(DRAWER_DIMENSIONS_UNIT_INPUT)
        if drawerUnitInput:
            drawerUnitInput.isVisible = specify_by_mode == SPECIFY_BY_DRAWER
    except Exception as err:
        futil.log(f'{CMD_NAME} _update_main_dimensions_visibility: {err}')


def _sync_computed_grid_and_padding(inputs):
    """When mode is Drawer size or Print plate, compute grid + even padding and write to plate/padding inputs."""
    try:
        specify_by = uiState.getState(SPECIFY_BY_MODE_INPUT)
        if specify_by not in (SPECIFY_BY_DRAWER, SPECIFY_BY_PRINT_PLATE):
            return
        base_width = uiState.getState(BASEPLATE_BASE_UNIT_WIDTH_INPUT)
        base_length = uiState.getState(BASEPLATE_BASE_UNIT_LENGTH_INPUT)
        xy_clearance = uiState.getState(BIN_XY_CLEARANCE_INPUT_ID)
        if specify_by == SPECIFY_BY_DRAWER:
            drawer_unit = uiState.getState(DRAWER_DIMENSIONS_UNIT_INPUT) if uiState.inputState.get(DRAWER_DIMENSIONS_UNIT_INPUT) else DRAWER_UNIT_INCHES
            target_width = _length_to_cm(uiState.getState(DRAWER_WIDTH_INPUT), drawer_unit)
            target_length = _length_to_cm(uiState.getState(DRAWER_LENGTH_INPUT), drawer_unit)
        else:
            pp_unit = uiState.getState(PRINT_PLATE_DIMENSIONS_UNIT_INPUT) if uiState.inputState.get(PRINT_PLATE_DIMENSIONS_UNIT_INPUT) else DRAWER_UNIT_MM
            target_width = _length_to_cm(uiState.getState(PRINT_PLATE_WIDTH_INPUT), pp_unit)
            target_length = _length_to_cm(uiState.getState(PRINT_PLATE_LENGTH_INPUT), pp_unit)
        (plate_w_u, plate_l_u, pad_l, pad_t, pad_r, pad_b) = drawerGridUtils.compute_grid_and_padding_from_drawer(
            target_width, target_length, base_width, base_length, xy_clearance
        )
        uiState.updateValue(BASEPLATE_WIDTH_INPUT, plate_w_u)
        uiState.updateValue(BASEPLATE_LENGTH_INPUT, plate_l_u)
        uiState.updateValue(BASEPLATE_WITH_SIDE_PADDING_INPUT, True)
        uiState.updateValue(BASEPLATE_SIDE_PADDING_LEFT_INPUT, pad_l)
        uiState.updateValue(BASEPLATE_SIDE_PADDING_TOP_INPUT, pad_t)
        uiState.updateValue(BASEPLATE_SIDE_PADDING_RIGHT_INPUT, pad_r)
        uiState.updateValue(BASEPLATE_SIDE_PADDING_BOTTOM_INPUT, pad_b)
        # Refresh inputs so UI shows the computed values
        for inp_id in (BASEPLATE_WIDTH_INPUT, BASEPLATE_LENGTH_INPUT, BASEPLATE_WITH_SIDE_PADDING_INPUT,
                       BASEPLATE_SIDE_PADDING_LEFT_INPUT, BASEPLATE_SIDE_PADDING_TOP_INPUT,
                       BASEPLATE_SIDE_PADDING_RIGHT_INPUT, BASEPLATE_SIDE_PADDING_BOTTOM_INPUT):
            if inp_id in uiState.commandInputs and uiState.inputState.get(inp_id):
                uiState.updateInputFromState(uiState.commandInputs[inp_id])
    except Exception as err:
        futil.log(f'{CMD_NAME} _sync_computed_grid_and_padding: {err}')


def getErrorMessage(text = "An unknown error occurred, please validate your inputs and try again"):
    stackTrace = traceback.format_exc()
    return f"{text}:<br>{stackTrace}"

def showErrorInMessageBox(text = "An unknown error occurred, please validate your inputs and try again"):
    if ui:
        ui.messageBox(getErrorMessage(text), f"{CMD_NAME} Error")

# Executed when add-in is run.
def start():
    futil.log(f'{CMD_NAME} Command Start Event')
    try:
        addinConfig = configUtils.readConfig(CONFIG_FOLDER_PATH)

        # Create a command Definition.
        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if not cmd_def:
            cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

            # Define an event handler for the command created event. It will be called when the button is clicked.
            futil.add_handler(cmd_def.commandCreated, command_created)

            # ******** Add a button into the UI so the user can run the command. ********
            # Get the target workspace the button will be created in.
            workspace = ui.workspaces.itemById(WORKSPACE_ID)

            # Get the panel the button will be created in.
            panel = workspace.toolbarPanels.itemById(PANEL_ID)

            # Create the button command control in the UI after the specified existing command.
            control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

            # Specify if the command is promoted to the main toolbar. 
            control.isPromoted = addinConfig['UI'].getboolean('is_promoted')

        initUiState()
        ui.statusMessage = ""
    except Exception as err:
        futil.log(f'{CMD_NAME} Error occurred at the start, {err}, {getErrorMessage()}')
        ui.statusMessage = f"{CMD_NAME} failed to initialize"
        showErrorInMessageBox(f"{CMD_NAME} Critical error occurred at the start, the command will be unavailable, if the issue persists use <a href=\"https://github.com/Le0Michine/FusionGridfinityGenerator/issues/new\">this link</a> to report it")


# Executed when add-in is stopped.
def stop():
    futil.log(f'{CMD_NAME} Command Stop Event')
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control: adsk.core.CommandControl = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    addinConfig = configUtils.readConfig(CONFIG_FOLDER_PATH)
    addinConfig['UI']['is_promoted'] = 'yes' if command_control.isPromoted else 'no'
    configUtils.writeConfig(addinConfig, CONFIG_FOLDER_PATH)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Created Event')
    global uiState

    args.command.setDialogInitialSize(420, 720)

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs
    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits

    infoGroup = inputs.addGroupCommandInput(INFO_GROUP, 'Info')
    infoGroup.isExpanded = uiState.getState(INFO_GROUP)
    uiState.registerCommandInput(infoGroup)
    infoGroup.children.addTextBoxCommandInput("info_text", "Info", INFO_TEXT, 3, True)

    basicSizesGroup = inputs.addGroupCommandInput(BASIC_SIZES_GROUP, 'Basic size')
    basicSizesGroup.isExpanded = uiState.getState(BASIC_SIZES_GROUP)
    uiState.registerCommandInput(basicSizesGroup)
    baseWidthUnitInput = basicSizesGroup.children.addValueInput(BASEPLATE_BASE_UNIT_WIDTH_INPUT, 'Base width unit, X (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_BASE_UNIT_WIDTH_INPUT)))
    baseWidthUnitInput.minimumValue = 1
    baseWidthUnitInput.isMinimumInclusive = True
    uiState.registerCommandInput(baseWidthUnitInput)
    baseLengthUnitInput = basicSizesGroup.children.addValueInput(BASEPLATE_BASE_UNIT_LENGTH_INPUT, 'Base length unit, Y (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_BASE_UNIT_LENGTH_INPUT)))
    baseLengthUnitInput.minimumValue = 1
    baseLengthUnitInput.isMinimumInclusive = True
    uiState.registerCommandInput(baseLengthUnitInput)

    xyClearanceInput = basicSizesGroup.children.addValueInput(BIN_XY_CLEARANCE_INPUT_ID, 'Bin xy clearance (mm)', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BIN_XY_CLEARANCE_INPUT_ID)))
    xyClearanceInput.minimumValue = 0.01
    xyClearanceInput.isMinimumInclusive = True
    xyClearanceInput.maximumValue = 0.05
    xyClearanceInput.isMaximumInclusive = True
    xyClearanceInput.tooltip = "Must be within range [0.1, 0.5]mm"
    uiState.registerCommandInput(xyClearanceInput)

    # Print plate dimensions (default 256x256 mm, e.g. Bambu P2S)
    printPlateGroup = basicSizesGroup.children.addGroupCommandInput('print_plate_group', 'Print plate')
    try:
        printPlateGroup.isExpanded = uiState.getState('print_plate_group')
    except (KeyError, TypeError):
        printPlateGroup.isExpanded = True  # expanded by default so width/length inputs are visible
    uiState.registerCommandInput(printPlateGroup)
    # Unitless inputs so value is the raw number (e.g. 256 mm); we convert using the unit dropdown.
    _ppw = uiState.getState(PRINT_PLATE_WIDTH_INPUT) if uiState.inputState.get(PRINT_PLATE_WIDTH_INPUT) else const.PRINT_PLATE_DEFAULT_WIDTH_MM
    _ppl = uiState.getState(PRINT_PLATE_LENGTH_INPUT) if uiState.inputState.get(PRINT_PLATE_LENGTH_INPUT) else const.PRINT_PLATE_DEFAULT_LENGTH_MM
    printPlateWidthInput = printPlateGroup.children.addValueInput(PRINT_PLATE_WIDTH_INPUT, 'Print plate width', '', adsk.core.ValueInput.createByReal(_ppw))
    printPlateWidthInput.minimumValue = 0.1
    printPlateWidthInput.isMinimumInclusive = True
    printPlateWidthInput.tooltip = "Value in the unit selected below (Inches or mm)"
    uiState.registerCommandInput(printPlateWidthInput)
    printPlateLengthInput = printPlateGroup.children.addValueInput(PRINT_PLATE_LENGTH_INPUT, 'Print plate length', '', adsk.core.ValueInput.createByReal(_ppl))
    printPlateLengthInput.minimumValue = 0.1
    printPlateLengthInput.isMinimumInclusive = True
    printPlateLengthInput.tooltip = "Value in the unit selected below (Inches or mm)"
    uiState.registerCommandInput(printPlateLengthInput)
    try:
        _pp_unit = uiState.getState(PRINT_PLATE_DIMENSIONS_UNIT_INPUT)
    except (KeyError, TypeError):
        _pp_unit = DRAWER_UNIT_MM
    printPlateUnitDropdown = printPlateGroup.children.addDropDownCommandInput(PRINT_PLATE_DIMENSIONS_UNIT_INPUT, 'Print plate dimensions unit', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    printPlateUnitDropdown.listItems.add(DRAWER_UNIT_INCHES, _pp_unit == DRAWER_UNIT_INCHES)
    printPlateUnitDropdown.listItems.add(DRAWER_UNIT_MM, _pp_unit == DRAWER_UNIT_MM)
    printPlateUnitDropdown.tooltip = "Unit for Print plate width and length above"
    uiState.registerCommandInput(printPlateUnitDropdown)

    mainDimensionsGroup = inputs.addGroupCommandInput(XY_DIMENSIONS_GROUP, 'Main dimensions')
    mainDimensionsGroup.isExpanded = uiState.getState(XY_DIMENSIONS_GROUP)
    uiState.registerCommandInput(mainDimensionsGroup)
    specifyByDropdown = mainDimensionsGroup.children.addDropDownCommandInput(SPECIFY_BY_MODE_INPUT, 'Specify by', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    try:
        specify_by_state = uiState.getState(SPECIFY_BY_MODE_INPUT)
    except (KeyError, TypeError):
        specify_by_state = SPECIFY_BY_UNITS
    specifyByDropdown.listItems.add(SPECIFY_BY_UNITS, specify_by_state == SPECIFY_BY_UNITS)
    specifyByDropdown.listItems.add(SPECIFY_BY_DRAWER, specify_by_state == SPECIFY_BY_DRAWER)
    specifyByDropdown.listItems.add(SPECIFY_BY_PRINT_PLATE, specify_by_state == SPECIFY_BY_PRINT_PLATE)
    uiState.registerCommandInput(specifyByDropdown)
    baseplateWidthInput = mainDimensionsGroup.children.addIntegerSpinnerCommandInput(BASEPLATE_WIDTH_INPUT, 'Plate width, X (u)', 1, 100, 1, uiState.getState(BASEPLATE_WIDTH_INPUT))
    uiState.registerCommandInput(baseplateWidthInput)
    baseplateLengthInput = mainDimensionsGroup.children.addIntegerSpinnerCommandInput(BASEPLATE_LENGTH_INPUT, 'Plate length, Y (u)', 1, 100, 1, uiState.getState(BASEPLATE_LENGTH_INPUT))
    uiState.registerCommandInput(baseplateLengthInput)
    # Unitless inputs so value is the raw number (e.g. 254 mm or 10 in); we convert using the unit dropdown.
    _dw = uiState.getState(DRAWER_WIDTH_INPUT) if uiState.inputState.get(DRAWER_WIDTH_INPUT) else 10.0
    _dl = uiState.getState(DRAWER_LENGTH_INPUT) if uiState.inputState.get(DRAWER_LENGTH_INPUT) else 18.0
    drawerWidthInput = mainDimensionsGroup.children.addValueInput(DRAWER_WIDTH_INPUT, 'Drawer width', '', adsk.core.ValueInput.createByReal(_dw))
    drawerWidthInput.minimumValue = 0.1
    drawerWidthInput.isMinimumInclusive = True
    drawerWidthInput.tooltip = "Value in the unit selected below (Inches or mm)"
    uiState.registerCommandInput(drawerWidthInput)
    drawerLengthInput = mainDimensionsGroup.children.addValueInput(DRAWER_LENGTH_INPUT, 'Drawer length', '', adsk.core.ValueInput.createByReal(_dl))
    drawerLengthInput.minimumValue = 0.1
    drawerLengthInput.isMinimumInclusive = True
    drawerLengthInput.tooltip = "Value in the unit selected below (Inches or mm)"
    uiState.registerCommandInput(drawerLengthInput)
    drawerUnitDropdown = mainDimensionsGroup.children.addDropDownCommandInput(DRAWER_DIMENSIONS_UNIT_INPUT, 'Drawer dimensions unit', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    try:
        _drawer_unit = uiState.getState(DRAWER_DIMENSIONS_UNIT_INPUT)
    except (KeyError, TypeError):
        _drawer_unit = DRAWER_UNIT_INCHES
    drawerUnitDropdown.listItems.add(DRAWER_UNIT_INCHES, _drawer_unit == DRAWER_UNIT_INCHES)
    drawerUnitDropdown.listItems.add(DRAWER_UNIT_MM, _drawer_unit == DRAWER_UNIT_MM)
    drawerUnitDropdown.tooltip = "Unit for Drawer width and Drawer length above"
    uiState.registerCommandInput(drawerUnitDropdown)

    plateFeaturesGroup = inputs.addGroupCommandInput(PLATE_FEATURES_GROUP, 'Features')
    plateFeaturesGroup.isExpanded = uiState.getState(PLATE_FEATURES_GROUP)
    uiState.registerCommandInput(plateFeaturesGroup)
    plateTypeDropdown = plateFeaturesGroup.children.addDropDownCommandInput(BASEPLATE_TYPE_DROPDOWN, 'Baseplate type', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
    plateTypeDropdownInitialState = uiState.getState(BASEPLATE_TYPE_DROPDOWN)
    plateTypeDropdown.listItems.add(BASEPLATE_TYPE_LIGHT, plateTypeDropdownInitialState == BASEPLATE_TYPE_LIGHT)
    plateTypeDropdown.listItems.add(BASEPLATE_TYPE_SKELETONIZED, plateTypeDropdownInitialState == BASEPLATE_TYPE_SKELETONIZED)
    plateTypeDropdown.listItems.add(BASEPLATE_TYPE_FULL, plateTypeDropdownInitialState == BASEPLATE_TYPE_FULL)
    uiState.registerCommandInput(plateTypeDropdown)

    magnetCutoutGroup = plateFeaturesGroup.children.addGroupCommandInput(MAGNET_SOCKET_GROUP, 'Magnet cutouts')
    magnetCutoutGroup.isExpanded = uiState.getState(MAGNET_SOCKET_GROUP)
    uiState.registerCommandInput(magnetCutoutGroup)
    generateMagnetSocketInput = magnetCutoutGroup.children.addBoolValueInput(BASEPLATE_WITH_MAGNETS_INPUT, 'Add magnet cutouts', True, '', uiState.getState(BASEPLATE_WITH_MAGNETS_INPUT))
    uiState.registerCommandInput(generateMagnetSocketInput)
    magnetSocketDiameterInput = magnetCutoutGroup.children.addValueInput(BASEPLATE_MAGNET_DIAMETER_INPUT, 'Magnet cutout diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_MAGNET_DIAMETER_INPUT)))
    uiState.registerCommandInput(magnetSocketDiameterInput)
    magnetSocketDepthInput = magnetCutoutGroup.children.addValueInput(BASEPLATE_MAGNET_HEIGHT_INPUT, 'Magnet cutout depth', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_MAGNET_HEIGHT_INPUT)))
    uiState.registerCommandInput(magnetSocketDepthInput)

    screwHoleGroup = plateFeaturesGroup.children.addGroupCommandInput(SCREW_HOLE_GROUP, 'Screw holes')
    screwHoleGroup.isExpanded = uiState.getState(SCREW_HOLE_GROUP)
    uiState.registerCommandInput(screwHoleGroup)
    generateScrewHolesInput = screwHoleGroup.children.addBoolValueInput(BASEPLATE_WITH_SCREWS_INPUT, 'Add screw holes', True, '', uiState.getState(BASEPLATE_WITH_SCREWS_INPUT))
    uiState.registerCommandInput(generateScrewHolesInput)
    screwSizeInput = screwHoleGroup.children.addValueInput(BASEPLATE_SCREW_DIAMETER_INPUT, 'Screw hole diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_SCREW_DIAMETER_INPUT)))
    screwSizeInput.minimumValue = 0.1
    screwSizeInput.isMinimumInclusive = True
    screwSizeInput.maximumValue = 1
    screwSizeInput.isMaximumInclusive = True
    uiState.registerCommandInput(screwSizeInput)

    screwHeadSizeInput = screwHoleGroup.children.addValueInput(BASEPLATE_SCREW_HEIGHT_INPUT, 'Screw head cutout diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_SCREW_HEIGHT_INPUT)))
    screwHeadSizeInput.minimumValue = 0.2
    screwHeadSizeInput.isMinimumInclusive = True
    screwHeadSizeInput.maximumValue = 1.5
    screwHeadSizeInput.isMaximumInclusive = True
    screwHeadSizeInput.tooltip = "Must be greater than screw diameter"
    uiState.registerCommandInput(screwHeadSizeInput)

    sidePaddingGroup = plateFeaturesGroup.children.addGroupCommandInput(SIDE_PADDING_GROUP, 'Side padding')
    sidePaddingGroup.isExpanded = uiState.getState(SIDE_PADDING_GROUP)
    uiState.registerCommandInput(sidePaddingGroup)
    generateSidePaddingInput = sidePaddingGroup.children.addBoolValueInput(BASEPLATE_WITH_SIDE_PADDING_INPUT, 'Add side padding', True, '', uiState.getState(BASEPLATE_WITH_SIDE_PADDING_INPUT))
    uiState.registerCommandInput(generateSidePaddingInput)

    sidePaddingLeftInput = sidePaddingGroup.children.addValueInput(BASEPLATE_SIDE_PADDING_LEFT_INPUT, 'Padding left', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_SIDE_PADDING_LEFT_INPUT)))
    sidePaddingLeftInput.minimumValue = 0
    sidePaddingLeftInput.isMinimumInclusive = True
    sidePaddingLeftInput.tooltip = "Must be equal or greater than 0"
    uiState.registerCommandInput(sidePaddingLeftInput)

    sidePaddingTopInput = sidePaddingGroup.children.addValueInput(BASEPLATE_SIDE_PADDING_TOP_INPUT, 'Padding top', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_SIDE_PADDING_TOP_INPUT)))
    sidePaddingTopInput.minimumValue = 0
    sidePaddingTopInput.isMinimumInclusive = True
    sidePaddingTopInput.tooltip = "Must be equal or greater than 0"
    uiState.registerCommandInput(sidePaddingTopInput)

    sidePaddingRightInput = sidePaddingGroup.children.addValueInput(BASEPLATE_SIDE_PADDING_RIGHT_INPUT, 'Padding right', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_SIDE_PADDING_RIGHT_INPUT)))
    sidePaddingRightInput.minimumValue = 0
    sidePaddingRightInput.isMinimumInclusive = True
    sidePaddingRightInput.tooltip = "Must be equal or greater than 0"
    uiState.registerCommandInput(sidePaddingRightInput)

    sidePaddingBottomInput = sidePaddingGroup.children.addValueInput(BASEPLATE_SIDE_PADDING_BOTTOM_INPUT, 'Padding bottom', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_SIDE_PADDING_BOTTOM_INPUT)))
    sidePaddingBottomInput.minimumValue = 0
    sidePaddingBottomInput.isMinimumInclusive = True
    sidePaddingBottomInput.tooltip = "Must be equal or greater than 0"
    uiState.registerCommandInput(sidePaddingBottomInput)

    advancedPlateSizeGroup = plateFeaturesGroup.children.addGroupCommandInput(ADVANCED_PLATE_SIZE_GROUP, 'Advanced plate size options')
    advancedPlateSizeGroup.isExpanded = uiState.getState(ADVANCED_PLATE_SIZE_GROUP)
    uiState.registerCommandInput(advancedPlateSizeGroup)
    extraBottomThicknessInput = advancedPlateSizeGroup.children.addValueInput(BASEPLATE_EXTRA_THICKNESS_INPUT, 'Extra bottom thickness', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_EXTRA_THICKNESS_INPUT)))
    extraBottomThicknessInput.minimumValue = 0
    extraBottomThicknessInput.isMinimumInclusive = False
    uiState.registerCommandInput(extraBottomThicknessInput)

    verticalClearanceInput = advancedPlateSizeGroup.children.addValueInput(BASEPLATE_BIN_Z_CLEARANCE_INPUT, 'Clearance between baseplate and bin', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_BIN_Z_CLEARANCE_INPUT)))
    verticalClearanceInput.minimumValue = 0
    verticalClearanceInput.isMinimumInclusive = True
    verticalClearanceInput.maximumValue = 0.3
    verticalClearanceInput.isMaximumInclusive = True
    uiState.registerCommandInput(verticalClearanceInput)
    
    generateBaseplateConnectionPinHoleInput = advancedPlateSizeGroup.children.addBoolValueInput(BASEPLATE_HAS_CONNECTION_HOLE_INPUT, 'Add connection holes',  True, '', uiState.getState(BASEPLATE_HAS_CONNECTION_HOLE_INPUT))
    uiState.registerCommandInput(generateBaseplateConnectionPinHoleInput)
    connectionHoleSizeInput = advancedPlateSizeGroup.children.addValueInput(BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT, 'Connection hole diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(uiState.getState(BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT)))
    connectionHoleSizeInput.minimumValue = 0.1
    connectionHoleSizeInput.isMinimumInclusive = True
    connectionHoleSizeInput.maximumValue = 0.5
    connectionHoleSizeInput.isMaximumInclusive = True
    uiState.registerCommandInput(connectionHoleSizeInput)
    
    inputChangesGroup = inputs.addGroupCommandInput(INPUT_CHANGES_GROUP, 'Inputs')
    inputChangesGroup.isExpanded = uiState.getState(INPUT_CHANGES_GROUP)
    uiState.registerCommandInput(inputChangesGroup)
    saveAsDefaultsButtonInput = inputChangesGroup.children.addBoolValueInput(INPUT_CHANGES_SAVE_DEFAULTS, 'Save as new defaults', False, '', False)
    saveAsDefaultsButtonInput.text = 'Save'
    resetToDefaultsButtonInput = inputChangesGroup.children.addBoolValueInput(INPUT_CHANGES_RESET_TO_DEFAULTS, 'Reset to defaults', False, '', False)
    resetToDefaultsButtonInput.text = 'Reset'
    factoryResetButtonInput = inputChangesGroup.children.addBoolValueInput(INPUT_CHANGES_RESET_TO_FACTORY, 'Wipe saved settings', False, '', False)
    factoryResetButtonInput.text = 'Factory reset'

    previewGroup = inputs.addGroupCommandInput(PREVIEW_GROUP, 'Preview')
    uiState.registerCommandInput(previewGroup)
    previewGroup.isExpanded = uiState.getState(PREVIEW_GROUP)
    showLivePreview = previewGroup.children.addBoolValueInput(SHOW_PREVIEW_INPUT, 'Show preview (slow)', True, '', uiState.getState(SHOW_PREVIEW_INPUT))
    uiState.registerCommandInput(showLivePreview)

    exportGroup = inputs.addGroupCommandInput(EXPORT_GROUP, 'Export')
    exportGroup.isExpanded = uiState.getState(EXPORT_GROUP)
    uiState.registerCommandInput(exportGroup)
    exportInfo = exportGroup.children.addTextBoxCommandInput(
        EXPORT_INFO_INPUT,
        '',
        'Export each generated plate body as its own numbered STL file.',
        1,
        True,
    )
    uiState.registerCommandInput(exportInfo)
    exportButton = exportGroup.children.addBoolValueInput(EXPORT_STL_INPUT, 'Export split plates as STL files', False, '', False)
    exportButton.text = 'Export STLs'
    uiState.registerCommandInput(exportButton)

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

    # Set initial visibility for main dimensions and sync computed values if in drawer/print-plate mode
    try:
        specify_by = uiState.getState(SPECIFY_BY_MODE_INPUT)
        _update_main_dimensions_visibility(inputs, specify_by)
        _sync_computed_grid_and_padding(inputs)
    except Exception:
        pass


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')
    generateBaseplate(args)


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Preview Event')
    # Get a reference to command's inputs.
    inputs = args.command.commandInputs
    showPreview: adsk.core.BoolValueCommandInput = inputs.itemById(SHOW_PREVIEW_INPUT)
    if showPreview.value:
        if INPUTS_VALID:
            generateBaseplate(args)
        else:
            args.executeFailed = True
            args.executeFailedMessage = "Some inputs are invalid, unable to generate preview"


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    global uiState
    inputs = args.inputs
    if changed_input.id == INPUT_CHANGES_SAVE_DEFAULTS:
        saveUIInputsAsDefaults()
    elif changed_input.id == EXPORT_STL_INPUT:
        changed_input.value = False
        if not INPUTS_VALID:
            ui.messageBox('Some inputs are invalid, unable to export STL files.', 'GridfinityGeneratorMod Export')
            return
        try:
            _export_baseplate_stls()
        except UnsupportedDesignTypeException:
            ui.messageBox(
                'Design type is unsupported. Projects with disabled design history are unsupported, please enable timeline feature to proceed.',
                'GridfinityGeneratorMod Export'
            )
        except Exception as err:
            futil.log(f'{CMD_NAME} STL export failed: {err}, {getErrorMessage()}')
            ui.messageBox(getErrorMessage('Failed to export STL files'), 'GridfinityGeneratorMod Export')
        return
    elif changed_input.id == INPUT_CHANGES_RESET_TO_DEFAULTS:
        initUiState()
        uiState.forceUIRefresh()
    elif changed_input.id == INPUT_CHANGES_RESET_TO_FACTORY:
        configUtils.deleteConfigFile(UI_INPUT_DEFAULTS_CONFIG_PATH)
        initUiState()
        uiState.forceUIRefresh()
    else:
        uiState.onInputUpdate(changed_input)

    # Update main dimensions visibility and sync computed grid/padding when mode or dimensions change
    changed_id = changed_input.id
    if changed_id == SPECIFY_BY_MODE_INPUT or changed_id in (
        DRAWER_WIDTH_INPUT, DRAWER_LENGTH_INPUT, DRAWER_DIMENSIONS_UNIT_INPUT,
        PRINT_PLATE_WIDTH_INPUT, PRINT_PLATE_LENGTH_INPUT, PRINT_PLATE_DIMENSIONS_UNIT_INPUT,
        BASEPLATE_BASE_UNIT_WIDTH_INPUT, BASEPLATE_BASE_UNIT_LENGTH_INPUT, BIN_XY_CLEARANCE_INPUT_ID
    ):
        try:
            specify_by = uiState.getState(SPECIFY_BY_MODE_INPUT)
            _update_main_dimensions_visibility(inputs, specify_by)
            _sync_computed_grid_and_padding(inputs)
        except Exception:
            pass

    if isinstance(changed_input, adsk.core.GroupCommandInput) and changed_input.isExpanded == True:
        for input in changed_input.children:
            uiState.registerCommandInput(input)
        uiState.forceUIRefresh()

    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    global INPUTS_VALID
    # General logging for debug.
    futil.log(f'{CMD_NAME} Validate Input Event')

    inputsState = getInputsState()
    specify_by = uiState.getState(SPECIFY_BY_MODE_INPUT) if uiState.inputState.get(SPECIFY_BY_MODE_INPUT) else SPECIFY_BY_UNITS

    # Mode-specific checks: drawer/print plate dimensions > 0 when in those modes
    mode_ok = True
    if specify_by == SPECIFY_BY_DRAWER:
        try:
            dw = uiState.getState(DRAWER_WIDTH_INPUT)
            dl = uiState.getState(DRAWER_LENGTH_INPUT)
            mode_ok = dw > 0 and dl > 0
        except (KeyError, TypeError):
            mode_ok = False
    elif specify_by == SPECIFY_BY_PRINT_PLATE:
        try:
            pw = uiState.getState(PRINT_PLATE_WIDTH_INPUT)
            pl = uiState.getState(PRINT_PLATE_LENGTH_INPUT)
            mode_ok = pw > 0 and pl > 0
        except (KeyError, TypeError):
            mode_ok = False

    # Verify the validity of the input values. This controls if the OK button is enabled or not.
    INPUTS_VALID = mode_ok \
        and inputsState.baseWidth >= 1 \
        and inputsState.baseLength >= 1 \
        and inputsState.xyClearance >= 0.01 \
        and inputsState.xyClearance <= 0.05 \
        and inputsState.plateWidth > 0 \
        and inputsState.plateLength > 0 \
        and (not inputsState.hasMagnetSockets or (inputsState.magnetSocketSize <= 1 and inputsState.magnetSocketSize > 0 and inputsState.magnetSocketDepth > 0)) \
        and (not inputsState.hasScrewHoles or (inputsState.screwHoleSize > 0 and inputsState.screwHoleSize <= 1 and inputsState.screwHeadSize > inputsState.screwHoleSize and inputsState.screwHeadSize <= 1.5)) \
        and (not inputsState.hasConnectionHoles or (inputsState.connectionHoleSize > 0 and inputsState.connectionHoleSize <= 0.5)) \
        and (inputsState.extraBottomThickness > 0)

    args.areInputsValid = INPUTS_VALID

    # When plate exceeds print bed, we split into multiple plates; inform the user
    try:
        print_w, print_l = _get_print_plate_cm()
        total_w = inputsState.plateWidth * inputsState.baseWidth - 2 * inputsState.xyClearance + inputsState.paddingLeft + inputsState.paddingRight
        total_l = inputsState.plateLength * inputsState.baseLength - 2 * inputsState.xyClearance + inputsState.paddingTop + inputsState.paddingBottom
        if print_w > 0 and print_l > 0 and (total_w > print_w or total_l > print_l):
            num_x, num_y, _, _ = drawerGridUtils.compute_plate_split(
                int(inputsState.plateWidth), int(inputsState.plateLength),
                print_w, print_l, inputsState.baseWidth, inputsState.baseLength, inputsState.xyClearance,
            )
            num_plates = num_x * num_y
            args.validationMessage = (
                'Baseplate exceeds the size for a single print plate and has been split into {} plates. '
                'Each plate will fit on your build plate.'
            ).format(num_plates)
    except (KeyError, TypeError):
        pass
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Destroy Event')
    global local_handlers
    local_handlers = []
    global uiState


def generateBaseplate(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Generating baseplate')
    try:
        buildResult = _build_baseplate()
        des = buildResult['design']
        if des.designType == adsk.fusion.DesignTypes.ParametricDesignType:
            plateGroup = des.timeline.timelineGroups.add(buildResult['timeline_start'], des.timeline.count - 1)
            plateGroup.name = buildResult['name']
    except UnsupportedDesignTypeException as err:
        args.executeFailed = True
        args.executeFailedMessage = 'Design type is unsupported. Projects with disabled design history are unsupported, please enable timeline feature to proceed.'
        return False
    except Exception as err:
        args.executeFailed = True
        args.executeFailedMessage = getErrorMessage()
        futil.log(f'{CMD_NAME} Error occurred, {err}, {getErrorMessage()}')
        return False

def initUiState():
    global uiState
    uiState.initValue(INFO_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(BASIC_SIZES_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(XY_DIMENSIONS_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(PLATE_FEATURES_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(MAGNET_SOCKET_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(SCREW_HOLE_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(ADVANCED_PLATE_SIZE_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(INPUT_CHANGES_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(SIDE_PADDING_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(PREVIEW_GROUP, True, adsk.core.GroupCommandInput.classType())
    uiState.initValue(EXPORT_GROUP, True, adsk.core.GroupCommandInput.classType())

    uiState.initValue(BASEPLATE_BASE_UNIT_WIDTH_INPUT, DIMENSION_DEFAULT_WIDTH_UNIT, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_BASE_UNIT_LENGTH_INPUT, DIMENSION_DEFAULT_WIDTH_UNIT, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BIN_XY_CLEARANCE_INPUT_ID, const.BIN_XY_CLEARANCE, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_WIDTH_INPUT, 2, adsk.core.IntegerSpinnerCommandInput.classType())
    uiState.initValue(BASEPLATE_LENGTH_INPUT, 3, adsk.core.IntegerSpinnerCommandInput.classType())
    uiState.initValue(BASEPLATE_TYPE_DROPDOWN, BASEPLATE_TYPE_LIGHT, adsk.core.DropDownCommandInput.classType())

    uiState.initValue(BASEPLATE_WITH_MAGNETS_INPUT, True, adsk.core.BoolValueCommandInput.classType())

    uiState.initValue(BASEPLATE_MAGNET_DIAMETER_INPUT, const.DIMENSION_MAGNET_CUTOUT_DIAMETER, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_MAGNET_HEIGHT_INPUT, const.DIMENSION_MAGNET_CUTOUT_DEPTH, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_WITH_SCREWS_INPUT, True, adsk.core.BoolValueCommandInput.classType())

    uiState.initValue(BASEPLATE_WITH_SIDE_PADDING_INPUT, False, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(BASEPLATE_SIDE_PADDING_LEFT_INPUT, 0, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(BASEPLATE_SIDE_PADDING_TOP_INPUT, 0, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(BASEPLATE_SIDE_PADDING_RIGHT_INPUT, 0, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(BASEPLATE_SIDE_PADDING_BOTTOM_INPUT, 0, adsk.core.BoolValueCommandInput.classType())

    uiState.initValue(BASEPLATE_SCREW_DIAMETER_INPUT, const.DIMENSION_PLATE_SCREW_HOLE_DIAMETER, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_SCREW_HEIGHT_INPUT, const.DIMENSION_SCREW_HEAD_CUTOUT_DIAMETER, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_EXTRA_THICKNESS_INPUT, const.BASEPLATE_EXTRA_HEIGHT, adsk.core.ValueCommandInput.classType())

    uiState.initValue(BASEPLATE_BIN_Z_CLEARANCE_INPUT, const.BASEPLATE_BIN_Z_CLEARANCE, adsk.core.ValueCommandInput.classType())
    uiState.initValue(BASEPLATE_HAS_CONNECTION_HOLE_INPUT, False, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT, const.DIMENSION_PLATE_CONNECTION_SCREW_HOLE_DIAMETER, adsk.core.ValueCommandInput.classType())
    uiState.initValue(SHOW_PREVIEW_INPUT, False, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(EXPORT_STL_INPUT, False, adsk.core.BoolValueCommandInput.classType())
    uiState.initValue(EXPORT_INFO_INPUT, 'Export each generated plate body as its own numbered STL file.', adsk.core.TextBoxCommandInput.classType())

    recordedDefaults = configUtils.readJsonConfig(UI_INPUT_DEFAULTS_CONFIG_PATH)
    if recordedDefaults:
        futil.log(f'{CMD_NAME} Found previously saving default values, restoring {recordedDefaults}')

        try:
            uiState.initValues(recordedDefaults)
            futil.log(f'{CMD_NAME} Successfully restored default values')
        except Exception as err:
            futil.log(f'{CMD_NAME} Failed to restore default values, err: {err}')


    else:
        futil.log(f'{CMD_NAME} No previously saved default values')

    # Ensure new inputs exist (in case they weren't in saved defaults)
    if not uiState.inputState.get('print_plate_group'):
        uiState.initValue('print_plate_group', True, adsk.core.GroupCommandInput.classType())
    if not uiState.inputState.get(PRINT_PLATE_WIDTH_INPUT):
        uiState.initValue(PRINT_PLATE_WIDTH_INPUT, float(const.PRINT_PLATE_DEFAULT_WIDTH_MM), adsk.core.ValueCommandInput.classType())
    if not uiState.inputState.get(PRINT_PLATE_LENGTH_INPUT):
        uiState.initValue(PRINT_PLATE_LENGTH_INPUT, float(const.PRINT_PLATE_DEFAULT_LENGTH_MM), adsk.core.ValueCommandInput.classType())
    if not uiState.inputState.get(SPECIFY_BY_MODE_INPUT):
        uiState.initValue(SPECIFY_BY_MODE_INPUT, SPECIFY_BY_UNITS, adsk.core.DropDownCommandInput.classType())
    if not uiState.inputState.get(DRAWER_WIDTH_INPUT):
        uiState.initValue(DRAWER_WIDTH_INPUT, 10.0, adsk.core.ValueCommandInput.classType())  # default 10 (inches or mm per unit dropdown)
    if not uiState.inputState.get(DRAWER_LENGTH_INPUT):
        uiState.initValue(DRAWER_LENGTH_INPUT, 18.0, adsk.core.ValueCommandInput.classType())  # default 18 (e.g. 10" x 18" drawer)
    if not uiState.inputState.get(DRAWER_DIMENSIONS_UNIT_INPUT):
        uiState.initValue(DRAWER_DIMENSIONS_UNIT_INPUT, DRAWER_UNIT_INCHES, adsk.core.DropDownCommandInput.classType())
    if not uiState.inputState.get(PRINT_PLATE_DIMENSIONS_UNIT_INPUT):
        uiState.initValue(PRINT_PLATE_DIMENSIONS_UNIT_INPUT, DRAWER_UNIT_MM, adsk.core.DropDownCommandInput.classType())

def saveUIInputsAsDefaults():
    futil.log(f'{CMD_NAME} Saving UI state to file')
    result = configUtils.dumpJsonConfig(UI_INPUT_DEFAULTS_CONFIG_PATH, uiState.toDict())
    if result:
        futil.log(f'{CMD_NAME} Saved successfully')
    else:
        futil.log(f'{CMD_NAME} UI state failed to save')

def getInputsState():
    global uiState
    base_width = uiState.getState(BASEPLATE_BASE_UNIT_WIDTH_INPUT)
    base_length = uiState.getState(BASEPLATE_BASE_UNIT_LENGTH_INPUT)
    xy_clearance = uiState.getState(BIN_XY_CLEARANCE_INPUT_ID)
    specify_by = uiState.getState(SPECIFY_BY_MODE_INPUT) if uiState.inputState.get(SPECIFY_BY_MODE_INPUT) else SPECIFY_BY_UNITS

    if specify_by == SPECIFY_BY_DRAWER:
        drawer_unit = uiState.getState(DRAWER_DIMENSIONS_UNIT_INPUT) if uiState.inputState.get(DRAWER_DIMENSIONS_UNIT_INPUT) else DRAWER_UNIT_INCHES
        target_width = _length_to_cm(uiState.getState(DRAWER_WIDTH_INPUT), drawer_unit)
        target_length = _length_to_cm(uiState.getState(DRAWER_LENGTH_INPUT), drawer_unit)
        (plate_width, plate_length, pad_l, pad_t, pad_r, pad_b) = drawerGridUtils.compute_grid_and_padding_from_drawer(
            target_width, target_length, base_width, base_length, xy_clearance
        )
        has_padding = True
    elif specify_by == SPECIFY_BY_PRINT_PLATE:
        pp_unit = uiState.getState(PRINT_PLATE_DIMENSIONS_UNIT_INPUT) if uiState.inputState.get(PRINT_PLATE_DIMENSIONS_UNIT_INPUT) else DRAWER_UNIT_MM
        target_width = _length_to_cm(uiState.getState(PRINT_PLATE_WIDTH_INPUT), pp_unit)
        target_length = _length_to_cm(uiState.getState(PRINT_PLATE_LENGTH_INPUT), pp_unit)
        (plate_width, plate_length, pad_l, pad_t, pad_r, pad_b) = drawerGridUtils.compute_grid_and_padding_from_drawer(
            target_width, target_length, base_width, base_length, xy_clearance
        )
        has_padding = True
    else:
        plate_width = uiState.getState(BASEPLATE_WIDTH_INPUT)
        plate_length = uiState.getState(BASEPLATE_LENGTH_INPUT)
        has_padding = uiState.getState(BASEPLATE_WITH_SIDE_PADDING_INPUT)
        pad_l = uiState.getState(BASEPLATE_SIDE_PADDING_LEFT_INPUT)
        pad_t = uiState.getState(BASEPLATE_SIDE_PADDING_TOP_INPUT)
        pad_r = uiState.getState(BASEPLATE_SIDE_PADDING_RIGHT_INPUT)
        pad_b = uiState.getState(BASEPLATE_SIDE_PADDING_BOTTOM_INPUT)

    return InputState(
        base_width,
        base_length,
        xy_clearance,
        plate_width,
        plate_length,
        uiState.getState(BASEPLATE_TYPE_DROPDOWN),
        uiState.getState(BASEPLATE_WITH_MAGNETS_INPUT),
        uiState.getState(BASEPLATE_MAGNET_DIAMETER_INPUT),
        uiState.getState(BASEPLATE_MAGNET_HEIGHT_INPUT),
        uiState.getState(BASEPLATE_WITH_SCREWS_INPUT),
        uiState.getState(BASEPLATE_SCREW_DIAMETER_INPUT),
        uiState.getState(BASEPLATE_SCREW_HEIGHT_INPUT),
        has_padding,
        pad_l,
        pad_t,
        pad_r,
        pad_b,
        uiState.getState(BASEPLATE_EXTRA_THICKNESS_INPUT),
        uiState.getState(BASEPLATE_BIN_Z_CLEARANCE_INPUT),
        uiState.getState(BASEPLATE_HAS_CONNECTION_HOLE_INPUT),
        uiState.getState(BASEPLATE_CONNECTION_HOLE_DIAMETER_INPUT),
    )