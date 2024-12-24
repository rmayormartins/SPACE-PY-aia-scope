import gradio as gr
from zipfile import ZipFile, BadZipFile
import tempfile
import os
import re
import pandas as pd
import collections
import json
import glob
from io import BytesIO

# Padrões de IA
ai_patterns = [
    "PIC*", "PersonalImageClassifier*", "Look*", "LookExtension*", "ChatBot", "ImageBot", "TMIC","Gemini*","Llama*","TeachableMachine*",
    "TeachableMachineImageClassifier*", "SpeechRecognizer*", "FaceExtension*","Pose*","Posenet","PosenetExtension", "Eliza*", "Alexa*"
]

# Padrões para cada categoria
drawing_and_animation_patterns = ["Ball", "Canvas", "ImageSprite"]
maps_patterns = ["Map", "Marker", "Circle", "FeatureCollection", "LineString", "Navigation","Polygon", "Retangle" ]
sensors_patterns = ["AccelerometerSensor", "BarcodeScanner", "Barometer", "Clock", "GyroscopeSensor", "Hygrometer", "LightSensor", "LocationSensor", "MagneticFieldSensor", "NearField","OrientationSensor", "ProximitySensor","Thermometer", "Pedometer"]
social_patterns = ["ContactPicker", "EmailPicker", "PhoneCall", "PhoneNumberPicker", "Texting", "Twitter"]
storage_patterns = ["File", "CloudDB", "DataFile", "Spreadsheet", "FusiontablesControl", "TinyDB", "TinyWebDB"]
connectivity_patterns = ["BluetoothClient", "ActivityStarter", "Serial", "BluetoothServer", "Web"]


def extract_components_using_regex(scm_content):
    pattern = r'"\$Type":"(.*?)"'
    components = re.findall(pattern, scm_content)
    if 'roboflow' in scm_content.lower():
        components.append("Using Roboflow")
    return components


def extract_category_components(components, patterns):
    category_components = []
    for component in components:
        for pattern in patterns:
            if component.startswith(pattern):
                category_components.append(component)
    return category_components


def extract_extensions_from_aia(file_path: str):
    extensions = []
    with ZipFile(file_path, 'r') as zip_ref:
        for file_path in zip_ref.namelist():
            if file_path.endswith('components.json') and 'assets/external_comps/' in file_path:
                with zip_ref.open(file_path) as file:
                    components_json_content = file.read().decode('utf-8', errors='ignore')
                    components_data = json.loads(components_json_content)
                    for component in components_data:
                        extension_type = component.get("type", "")
                        if extension_type:
                            extensions.append(extension_type)
    return extensions

def count_events_in_bky_file(bky_content):
    # Counting the number of occurrences of the "component_event" blocks
    return bky_content.count('<block type="component_event"')

def extract_app_name_from_scm_files(temp_dir):
    scm_files = glob.glob(f"{temp_dir}/src/appinventor/*/*/*.scm")
    for scm_file in scm_files:
        with open(scm_file, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()

            # Tenta várias expressões regulares para encontrar o nome do aplicativo
            regex_patterns = [
                r'"AppName"\s*:\s*"([^"]+)"',
                r'"AppName"\s*:\s*\'([^\']+)\''  # Exemplo de outra possível expressão regular
            ]

            for pattern in regex_patterns:
                app_name_match = re.search(pattern, content)
                if app_name_match:
                    return app_name_match.group(1)

    # Log de erros ou avisos
    print(f"Aviso: Nome do aplicativo não encontrado no diretório {temp_dir}")
    return "N/A"

def extract_project_info_from_properties(file_path):
    # Initialize variables
    timestamp = "N/A"
    app_name = "N/A"
    app_version = "N/A"
    authURL = "ai2.appinventor.mit.edu"

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        with ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            # Define the path to the 'project.properties' file
            project_properties_file_path = 'youngandroidproject/project.properties'

            # Check if the file exists in the .aia file
            if project_properties_file_path in zip_ref.namelist():
                with zip_ref.open(project_properties_file_path) as file:
                    project_properties_lines = file.read().decode('utf-8').splitlines()

                    # Extracting timestamp
                    timestamp = project_properties_lines[1] if len(project_properties_lines) > 1 else "N/A"

                    # Extracting app name and version using regular expressions
                    for line in project_properties_lines:
                        app_name_match = re.match(r'aname=(.*)', line)
                        if app_name_match:
                            app_name = app_name_match.group(1)

                        app_version_match = re.match(r'versionname=(.*)', line)
                        if app_version_match:
                            app_version = app_version_match.group(1)

        # Complementary method for extracting the app name from .scm files
        if app_name == "N/A":
         print("O campo App Name não foi encontrado em project.properties. Tentando encontrar em arquivos .scm...")
        app_name = extract_app_name_from_scm_files(temp_dir)
        print(f"Nome do App encontrado nos arquivos .scm: {app_name}")

    # ...


    return {
        'timestamp': timestamp,
        'app_name': app_name,
        'app_version': app_version,
        'authURL': authURL
    }





def extract_ai_components(components):
    ai_components = []
    for component in components:
        for pattern in ai_patterns:
            if '*' in pattern and component.startswith(pattern[:-1]):
                ai_components.append(component)
            elif component == pattern:
                ai_components.append(component)
    if "roboflow" in ' '.join(components).lower():
        ai_components.append("Using Roboflow")
    return ai_components

def extract_media_files(file_path: str):
    media_files = []
    with ZipFile(file_path, 'r') as zip_ref:
        for file_path in zip_ref.namelist():
            if 'assets/' in file_path and not file_path.endswith('/'):
                media_files.append(os.path.basename(file_path))
    return media_files

def list_components_in_aia_file(file_path):
    # 
    results_df = pd.DataFrame(columns=[
        'aia_file', 'project_info', 'components', 'IA components', 'screens', 'operators',
        'variables', 'events', 'extensions', 'Media',
        'Drawing and Animation', 'Maps', 'Sensors', 'Social', 'Storage', 'Connectivity'])


    pd.set_option('display.max_colwidth', None)
    file_name = os.path.basename(file_path)
    # 

    components_list = []
    number_of_screens = 0
    operators_count = 0
    variables_count = 0
    events_count = 0 # 
    # 
    media_files = extract_media_files(file_path)
    media_summary = ', '.join(media_files)
    # 
    project_info = extract_project_info_from_properties(file_path)
    project_info_str = f"Timestamp: {project_info['timestamp']}, App Name: {project_info['app_name']}, Version: {project_info['app_version']}, AuthURL: {project_info['authURL']}"


    with tempfile.TemporaryDirectory() as temp_dir:
        with ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        scm_files = glob.glob(temp_dir + '/src/appinventor/*/*/*.scm')
        bky_files = glob.glob(temp_dir + '/src/appinventor/*/*/*.bky') # Esta linha define bky_files

        number_of_screens = len(scm_files)
        for scm_file in scm_files:
            with open(scm_file, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
                components = extract_components_using_regex(content)
                components_list.extend(components)
                operators_count += len(re.findall(r'[+\-*/<>!=&|]', content))
                variables_count += len(re.findall(r'"\$Name":"(.*?)"', content))

        # 
        drawing_and_animation_summary = ', '.join(extract_category_components(components_list, drawing_and_animation_patterns))
        maps_summary = ', '.join(extract_category_components(components_list, maps_patterns))
        sensors_summary = ', '.join(extract_category_components(components_list, sensors_patterns))
        social_summary = ', '.join(extract_category_components(components_list, social_patterns))
        storage_summary = ', '.join(extract_category_components(components_list, storage_patterns))
        connectivity_summary = ', '.join(extract_category_components(components_list, connectivity_patterns))


        # 
        # 
        extensions_list = []
        extensions_list = extract_extensions_from_aia(file_path)

        for bky_file in bky_files:
            with open(bky_file, 'r', encoding='utf-8', errors='ignore') as file:
                bky_content = file.read()
                events_count += count_events_in_bky_file(bky_content)
                #


        # 
        extensions_summary = ', '.join(list(set(extensions_list)))

    components_count = collections.Counter(components_list)
    components_summary = [f'{comp} ({count} x)' if count > 1 else comp for comp, count in components_count.items()]
    ai_components_summary = extract_ai_components(components_list)
    new_row = pd.DataFrame([{
    'aia_file': file_name,
    'project_info': project_info_str,
    'components': ', '.join(components_summary),
    'IA components': ', '.join(ai_components_summary),
    'screens': number_of_screens,
    'operators': operators_count,
    'variables': variables_count,
    'events': events_count,
    'extensions': extensions_summary,
    'Media': media_summary,
    'Drawing and Animation': drawing_and_animation_summary,
    'Maps': maps_summary,
    'Sensors': sensors_summary,
    'Social': social_summary,
    'Storage': storage_summary,
    'Connectivity': connectivity_summary
    }])

    # 
    results_df = pd.concat([results_df, new_row], ignore_index=True)
    return results_df
#

# 
# 
output_style = """
<style>
    .output-container {
        max-height: 500px; /* a */
        overflow: auto; /* a */
        display: block; /* a */
    }
    .output-container table {
        width: 100%; /* a */
        border-collapse: collapse;
    }
    .output-container th, .output-container td {
        border: 1px solid #ddd; /* a */
        text-align: left;
        padding: 8px;
    }
</style>
"""

# 
def analyze_aia(uploaded_files):
    all_results = []
    for uploaded_file in uploaded_files:
        try:
            file_path = uploaded_file.name if hasattr(uploaded_file, 'name') else None
            if file_path and os.path.exists(file_path):
                with ZipFile(file_path, 'r') as zip_ref:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        zip_ref.extractall(temp_dir)
                        results_df = list_components_in_aia_file(file_path)
                        all_results.append(results_df)
            else:
                all_results.append(f"Não foi possível localizar o arquivo {file_path}.")
        except BadZipFile:
            all_results.append("Falha ao abrir o arquivo .aia como um arquivo zip.")
        except Exception as e:
            all_results.append(f"Erro ao processar o arquivo {file_path}: {str(e)}")

# 
    combined_results_df = pd.concat(all_results, ignore_index=True)
    html_result = combined_results_df.to_html(escape=False, classes="output-html")
    return output_style + f'<div class="output-container">{html_result}</div>'

iface = gr.Interface(
    fn=analyze_aia,
    inputs=gr.Files(label="Upload .aia Files"),  # 
    outputs=gr.HTML(),
    title="AIA-Scope",
    description="Upload .aia (or multiples .aia) files to analyze/dissect their components. An .aia file from MIT App Inventor is a project file format that contains all the necessary information for an App Inventor project.",
    live=False
)

if __name__ == "__main__":
    iface.launch(debug=True)



