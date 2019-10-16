import copy
import logging
import os
import pathlib
import argparse
import shutil
from dataclasses import dataclass
from xml.etree import ElementTree
from typing import Iterable, Tuple, Dict, Union


@dataclass
class RunConfiguration:
    nl2mat_file: str
    nl2sco_file: str
    nl2mat_target: str
    nl2sco_target: str
    scale: float

    @classmethod
    def from_args(cls, args=None):
        parser = argparse.ArgumentParser()
        parser.add_argument('nl2mat', nargs=1, type=str)
        parser.add_argument('--nl2sco', nargs=1, type=str)
        parser.add_argument('--scale', nargs=1, type=float)
        parser.add_argument('--nl2mat_target', nargs=1, type=str,
                            default='../resources/materials/')
        parser.add_argument('--nl2sco_target', nargs=1, type=str,
                            default='../')
        if args:
            arguments = parser.parse_args(args)
        else:
            arguments = parser.parse_args(args)
        return cls(
            arguments.nl2mat[0], arguments.nl2sco,
            arguments.nl2mat_target, arguments.nl2sco_target,
            arguments.scale,
        )


def get_template_files(path, identifier) -> Iterable[pathlib.Path]:
    return pathlib.Path(path).glob(f'{identifier}*.xml')


def get_referenced_textures(nl2mat_tree) -> Iterable[str]:
    map_nodes = nl2mat_tree.findall('./material/renderpass/texunit/map')
    return (node.text for node in map_nodes)


def copy_files(src_dst_list: Iterable[Tuple[pathlib.Path, pathlib.Path]]):
    for src, dst in src_dst_list:
        try:
            logging.info(f"copying {src} to {dst}")
            shutil.copy(str(src), str(dst))
        except Exception as exception:
            logging.error(
                f"skipping {src}, the following error occurred: {exception}")


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


def transform_to_target_file(
        template_file: pathlib.Path, replace_string: str, replaced_name: str,
        suffix: str, target_path: pathlib.Path
) -> pathlib.Path:
    new_file_path = template_file.with_name(
        template_file.name.replace(replace_string, replaced_name)
    )
    new_file_path = new_file_path.with_suffix(suffix)
    new_file_path = target_path / new_file_path.parts[-1]
    return new_file_path


def handle_materials(
        nl2mat_file: pathlib.Path,
        tc_templates: Iterable[pathlib.Path],
        material_name: str,
        target_path: pathlib.Path
):
    origin_path = nl2mat_file.parent
    nl2mat_tree: ElementTree.ElementTree = ElementTree.parse(nl2mat_file)
    texture_copies = (
        (origin_path / texture, target_path / texture)
        for texture in get_referenced_textures(nl2mat_tree)
    )
    copy_files(texture_copies)
    for template_file in tc_templates:
        target_nl2mat = transform_to_target_file(
            template_file,
            '[mat]', f'[{material_name}]', '.nl2mat',
            target_path
        )
        new_nl2mat_content = with_tc_info_from(
            template_file, nl2mat_tree
        )
        logging.info(f"creating {target_nl2mat}")
        new_nl2mat_content.write(target_nl2mat)


def read_content_of(template_file):
    with open(template_file) as handle:
        content = handle.read()
    return content


def write_content_to(content: str, file: Union[str, pathlib.Path]):
    with open(file, 'w') as handle:
        handle.write(content)


def with_applied_placeholders(
        template_file: pathlib.Path,
        replacements: Dict[str, str]
) -> str:
    content = read_content_of(template_file)
    for placeholder, replacement in replacements.items():
        content = content.replace(placeholder, replacement)
    return content


def create_nl2scos(
        source_sco: None,
        sco_templates: Iterable[pathlib.Path],
        material_name: str,
        target_path: pathlib.Path
):
    placeholders_replacements = {
        '{original_preview}': '',
        '{original_usercolors}': '',
        '{scale_settings}': '',
        '{material_name}': material_name
    }
    if source_sco:
        # TODO implement
        pass
    else:
        for sco_template in sco_templates:
            new_nl2sco_content = with_applied_placeholders(
                sco_template, placeholders_replacements
            )
            target_nl2sco = transform_to_target_file(
                sco_template,
                '[sco]', material_name.capitalize(), '.nl2sco',
                target_path
            )
            logging.info(f"creating {target_nl2sco}")
            write_content_to(new_nl2sco_content, target_nl2sco)


def main():
    logging.basicConfig(level=logging.INFO)
    run_config = RunConfiguration.from_args()

    mat_tc_templates = get_template_files('./_template', '[mat')
    mat_file = pathlib.Path(run_config.nl2mat_file)
    mat_target = pathlib.Path(run_config.nl2mat_target)
    material_name = mat_file.stem
    handle_materials(mat_file, mat_tc_templates, material_name, mat_target)

    sco_templates = get_template_files('./_template', '[sco')
    sco_target = pathlib.Path(run_config.nl2sco_target)
    create_nl2scos(
        None, sco_templates, material_name, sco_target
    )


if __name__ == '__main__':
    main()
