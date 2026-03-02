import os
import re
import glob

from ayon_core.pipeline import publish
from ayon_core.lib import (
    get_oiio_tool_args,
    run_subprocess,
)

def merge_textures(path, src_list, output, log):
    prefix = "MERGED__"
    env = os.environ.copy()
    oiio_tool_args = get_oiio_tool_args("oiiotool")

    src_path_list = [os.path.join(path, i) for i in src_list]
    output_path = os.path.join(path, prefix + output)

    over_list = []
    for src in src_path_list:
        oiio_info_cmd = oiio_tool_args + ["--info", "-v", src]
        result = run_subprocess(oiio_info_cmd, env=env)
        channels_match = re.search(r'channel list:\s*([^\n]+)', result)

        if channels_match:
            channels = channels_match.group(1)
            if (
                ', A' in channels
                or channels.endswith('A')
                or 'Alpha' in channels
            ):
                over_list.append(src)
            else:
                log.warn(f"{src} has no Alpha channel to be merged!")

    if over_list:
        oiio_over_cmd = oiio_tool_args + [over_list[0]]

        for src in over_list[1:]:
            oiio_over_cmd.extend([src, "--over"])

        oiio_over_cmd.extend(["-o", output_path])

        log.info(f"Running subprocess {oiio_over_cmd}")

        try:
            run_subprocess(oiio_over_cmd, env=env)
        except Exception as exc:
            raise RuntimeError(exc)
        finally:
            for src in src_path_list:
                merged = os.path.join(
                    path,
                    prefix + os.path.basename(src))

                try:
                    os.replace(merged, src)
                    log.info(f"Replaced map {merged} -> {src}")
                except FileNotFoundError:
                    os.remove(src)
                    log.info(f"Removed map {src}")

class ExtractTexturesAsSingleOutput(publish.Extractor):
    """Extract Texture As Single Output

    Combine the multliple texture sets into one single texture output.

    """
    enabled = True
    label = "Extract Texture Sets as Single Texture Output"
    hosts = ["substancepainter"]
    families = ["image"]
    settings_category = "substancepainter"

    # Run directly after textures export
    order = publish.Extractor.order - 0.0991

    def process(self, instance):
        if not instance.data.get("creator_attributes", {}).get(
            "flattenTextureSets", False):
            self.log.debug(
                "Skipping to export texture sets as single texture output.."
            )
            return

        reprs = instance.data["representations"]

        self.log.info(f"Representations - {reprs}")

        if reprs:
            staging_dir = instance.data["stagingDir"]
            repr_files = reprs[0]["files"]

            if isinstance(repr_files, str):
                repr_files = [repr_files]

            for dest in repr_files:
                base, ext = os.path.splitext(dest)
                source_image_outputs = glob.glob(
                    os.path.join(staging_dir, f"{base}*{ext}"))

                if source_image_outputs:
                    sources = [
                        os.path.basename(i) for i in source_image_outputs]
                    merge_textures(staging_dir, sources, dest, self.log)
                else:
                    self.log.warn(
                        f"Couldn't glob filename \
                        {base}*{ext} in {staging_dir}")
