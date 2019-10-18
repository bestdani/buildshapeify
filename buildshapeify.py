#! python3
import argparse
import copy
import datetime
import logging
import pathlib
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, Sequence, Tuple, Union
from xml.etree import ElementTree

TEMPLATE_SCO_IDENTIFIER = '[sco'
TEMPLATE_MAT_IDENTIFIER = '[mat'
TEMPLATE_DIR = './templates'

TUTORIAL_FILE = 'How to Use Buildshapeify.txt'
TUTORIAL_TEXT = """Buildshapeify by bestdani

To use this tool, you have to drag and drop files onto
the executable file.\n
You can drag and drop multiple single nl2mat files and simultaneously 
directories with nl2mat files and optionally a nl2sco file in them.\n
The optional nl2sco file will give the tool the required information to also 
include custom colors and preview files for the materials grouped in the 
same directory.\n
When the files have been dropped, new output files will be created in the
Scaleable Build Shapes directory, the nl2sco files can be used in NL2 and you
can also merge existing versions with your newly created version.\n
Run this tool from the command line with the -h option for more advanced
information when you want to change the output directories.\n
Always ensure the templates directory is next to the executable, advanced
users might want to modify these.\n
"""

if getattr(sys, 'frozen', False):
    exec_dir = pathlib.Path(sys.executable).parent.absolute()
elif __file__:
    exec_dir = pathlib.Path(__file__).parent.absolute()


@dataclass
class RunGroup:
    nl2sco_file: Union[None, pathlib.Path]
    nl2mat_files: Sequence[pathlib.Path]

    @classmethod
    def from_path_content(cls, path: pathlib.Path) -> 'RunGroup':
        nl2sco_files = tuple(path.glob('*.nl2sco'))
        nl2sco_file = nl2sco_files[0] if len(nl2sco_files) > 0 else None
        if len(nl2sco_files) > 1:
            logging.warning(
                f"Found more than one nl2sco file in the directory '{path}'."
                f" This might have undesired effects since only one can"
                f" be used!\n"

                f"> '{nl2sco_file.name}' has been picked."
            )
        nl2mat_files = tuple(path.glob('*.nl2mat'))
        return cls(nl2sco_file, nl2mat_files)

    @classmethod
    def groups_from_paths(
            cls, file_arguments: Sequence[str]
    ) -> Sequence['RunGroup']:

        ungrouped_nl2mats = []
        groups = [cls(None, ungrouped_nl2mats)]

        for file in file_arguments:
            path = pathlib.Path(file)
            if path.is_dir():
                group = RunGroup.from_path_content(path)
                if group.has_data():
                    groups.append(group)
            elif path.exists() and path.suffix == '.nl2mat':
                ungrouped_nl2mats.append(path)

        return groups

    def has_data(self) -> bool:
        return len(self.nl2mat_files) > 0


@dataclass
class RunConfiguration:
    run_groups: Sequence[RunGroup]
    nl2mat_dst: str
    nl2sco_dst: str
    preview_dst: str
    scale: float

    @classmethod
    def from_args(cls, args=None):
        parser = argparse.ArgumentParser()
        parser.add_argument('files', nargs='*')
        parser.add_argument('--scale', nargs=1, type=float)
        parser.add_argument(
            '--nl2mat_out', nargs=1, type=str,
            default='./Scaleable Build Shapes/'
                    'resources/materials/')
        parser.add_argument(
            '--nl2sco_out', nargs=1, type=str,
            default='./Scaleable Build Shapes/')
        parser.add_argument(
            '--preview_out', nargs=1, type=str,
            default='./Scaleable Build Shapes/'
                    'resources/previews/')
        if args:
            arguments = parser.parse_args(args)
        else:
            arguments = parser.parse_args(args)
        return cls(
            RunGroup.groups_from_paths(arguments.files),
            arguments.nl2mat_out, arguments.nl2sco_out,
            arguments.preview_out, arguments.scale,
        )


def read_content_of(template_file):
    with open(template_file) as handle:
        content = handle.read()
    return content


def copy_files(src_dst_list: Iterable[Tuple[pathlib.Path, pathlib.Path]]):
    for src, dst in src_dst_list:
        try:
            logging.info(f"copying {src} to {dst}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(str(src), str(dst))
        except OSError as exception:
            logging.warning(
                f"skipped {src}, since the file cannot be accessed "
                "(maybe it is referencing some internal file).\n"
                f"\tThe operating system gave the following warning:\n"
                f"\t{exception}"
            )
        except Exception as exception:
            logging.error(
                f"skipped {src}, the following error occurred:\n"
                f"\t{exception}")


def transform_to_dst_file(
        template_file: pathlib.Path, replace_string: str, replaced_name: str,
        suffix: str, dst_path: pathlib.Path
) -> pathlib.Path:
    new_file_path = template_file.with_name(
        template_file.name.replace(replace_string, replaced_name)
    )
    new_file_path = new_file_path.with_suffix(suffix)
    new_file_path = dst_path / new_file_path.parts[-1]
    return new_file_path


def write_content_to(content: str, file: Union[str, pathlib.Path]):
    with open(file, 'w') as handle:
        handle.write(content)


def with_tc_info_from(
        template_file: pathlib.Path, nl2mat_tree: ElementTree.ElementTree
) -> ElementTree.ElementTree:
    new_nl2mat_tree = copy.deepcopy(nl2mat_tree)
    template_tree = ElementTree.parse(template_file)
    template_texunit = template_tree.find('./material/renderpass/texunit')

    nl2mat_texunits = new_nl2mat_tree.findall('./material/renderpass/texunit')
    for texunit in nl2mat_texunits:
        texunit: ElementTree.Element
        for tc_entry in template_texunit:
            texunit.append(tc_entry)
    return new_nl2mat_tree


def with_applied_placeholders(
        template_file: pathlib.Path,
        replacements: Dict[str, str]
) -> str:
    content = read_content_of(template_file)
    for placeholder, replacement in replacements.items():
        content = content.replace(placeholder, replacement)
    return content


def create_nl2scos(
        sco_templates: Iterable[pathlib.Path],
        placeholders_replacements: Dict,
        material_name: str,
        dst_path: pathlib.Path
):
    for sco_template in sco_templates:
        new_nl2sco_content = with_applied_placeholders(
            sco_template, placeholders_replacements
        )
        dst_nl2sco = transform_to_dst_file(
            sco_template,
            '[sco]', material_name.capitalize(), '.nl2sco',
            dst_path
        )
        logging.info(f"creating {dst_nl2sco}")
        write_content_to(new_nl2sco_content, dst_nl2sco)


def get_referenced_textures(nl2mat_tree) -> Iterable[str]:
    map_nodes = nl2mat_tree.findall('./material/renderpass/texunit/map')
    return (node.text for node in map_nodes)


def handle_materials(
        nl2mat_file: pathlib.Path,
        tc_templates: Iterable[pathlib.Path],
        material_name: str,
        dst_path: pathlib.Path
):
    origin_path = nl2mat_file.parent
    nl2mat_tree: ElementTree.ElementTree = ElementTree.parse(nl2mat_file)
    texture_copies = (
        (origin_path / texture, dst_path / texture)
        for texture in get_referenced_textures(nl2mat_tree)
    )
    copy_files(texture_copies)
    for template_file in tc_templates:
        dst_nl2mat = transform_to_dst_file(
            template_file,
            '[mat]', f'[{material_name}]', '.nl2mat',
            dst_path
        )
        new_nl2mat_content = with_tc_info_from(
            template_file, nl2mat_tree
        )
        logging.info(f"creating {dst_nl2mat}")
        dst_nl2mat.parent.mkdir(parents=True, exist_ok=True)
        new_nl2mat_content.write(dst_nl2mat)


def get_sco_replacements(nl2sco_file, preview_dst, sco_dst):
    replacements = {
        '{preview}': '',
        '{original_usercolors}': '',
        '{scale_settings}': '',
        '{material_name}': ''
    }
    if nl2sco_file:
        sco_tree = ElementTree.parse(nl2sco_file)
        preview = sco_tree.find('./sceneobject/preview')
        if preview is not None:
            preview_src_file = nl2sco_file.parent / preview.text
            preview_dst_file = preview_dst / preview.text
            copy_files([(preview_src_file, preview_dst_file)])
            preview_text = preview_dst_file.relative_to(sco_dst).as_posix()
            replacements['{preview}'] = f"<preview>{preview_text}</preview>"

        usercolors = tuple(
            ElementTree.tostring(color, encoding='unicode')
            for color in sco_tree.findall('./sceneobject/usercolor')
        )
        if usercolors:
            replacements['{original_usercolors}'] = '\n'.join(usercolors)

    return replacements


def process_group_files(
        nl2mat_files, mat_tc_templates, mat_dst,
        nl2sco_file, sco_templates, sco_dst, preview_dst,
):
    sco_replacements = get_sco_replacements(
        nl2sco_file, preview_dst, sco_dst)

    for mat_file in nl2mat_files:
        material_name = mat_file.stem
        handle_materials(mat_file, mat_tc_templates, material_name, mat_dst)

        sco_replacements['{material_name}'] = material_name
        create_nl2scos(
            sco_templates, sco_replacements, material_name, sco_dst
        )


def run_for_config(run_config, mat_tc_templates, sco_templates):
    mat_dst = exec_dir / pathlib.Path(run_config.nl2mat_dst)
    sco_dst = exec_dir / pathlib.Path(run_config.nl2sco_dst)
    preview_dst = exec_dir / pathlib.Path(run_config.preview_dst)
    for group in run_config.run_groups:
        process_group_files(
            group.nl2mat_files, mat_tc_templates, mat_dst,
            group.nl2sco_file, sco_templates, sco_dst, preview_dst
        )


def get_template_files(path, identifier) -> Iterable[pathlib.Path]:
    return pathlib.Path(path).glob(f'{identifier}*.xml')


def setup_logging():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('')

    log_file_date = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_file = exec_dir / f"buildshapeify_{log_file_date}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)


def create_tutorial_file(tutorial_file: pathlib.Path):
    file = str(tutorial_file)
    with open(file, 'w') as handle:
        handle.write(TUTORIAL_TEXT)
    subprocess.Popen(('notepad', file))


def main():
    setup_logging()
    run_config = RunConfiguration.from_args()

    show_tutorial = (
            len(run_config.run_groups) == 1 and
            len(run_config.run_groups[0].nl2mat_files) == 0
    )

    if show_tutorial:
        logging.info("showing tutorial since no files have been dropped")
        create_tutorial_file(exec_dir / TUTORIAL_FILE)
    else:
        mat_tc_templates = tuple(get_template_files(
            exec_dir / TEMPLATE_DIR, TEMPLATE_MAT_IDENTIFIER))
        mat_template_printouts = "\n".join(
            f"\t{entry}" for entry in mat_tc_templates
        )
        logging.info(
            "found the following material templates:\n"
            f"{mat_template_printouts}"
        )

        sco_templates = tuple(get_template_files(
            exec_dir / TEMPLATE_DIR, TEMPLATE_SCO_IDENTIFIER))
        sco_template_printouts = "\n".join(
            f"\t{entry}" for entry in sco_templates
        )
        logging.info(
            "found the following sco templates:\n"
            f"{sco_template_printouts}"
        )

        run_for_config(run_config, mat_tc_templates, sco_templates)


if __name__ == '__main__':
    main()
