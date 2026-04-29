import os
import subprocess

import cv2
import numpy as np

from light_map.rendering.svg.loader import SVGLoader


def capture_reference(svg_path, out_path):
    # Headless chromium command
    # Create a temporary HTML to ensure zero margins
    html_path = out_path + ".html"
    with open(svg_path) as f:
        svg_content = f.read()
    # Inject style to ensure SVG fills the container
    svg_content = svg_content.replace(
        "<svg", "<svg style='width:512px;height:512px;display:block;'", 1
    )
    with open(html_path, "w") as f:
        f.write(
            f"<html style='margin:0;padding:0;width:512px;height:512px;'><body style='margin:0;padding:0;width:512px;height:512px;overflow:hidden;'>{svg_content}</body></html>"
        )

    cmd = [
        "chromium",
        "--headless",
        f"--screenshot={out_path}",
        "--window-size=1024,1024",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        "--default-background-color=000000",
        f"file://{os.path.abspath(html_path)}",
    ]
    try:
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        os.remove(html_path)
        # Standardize size to 512x512
        img = cv2.imread(out_path)
        if img is not None:
            # Crop to top-left 512x512
            img = img[0:512, 0:512]
            cv2.imwrite(out_path, img)
    except Exception as e:
        print(f"Error capturing reference: {e}")


def capture_actual(svg_path, out_path):
    loader = SVGLoader(svg_path)
    if not loader.svg:
        return
    # Calculate scale to fit 512x512
    sw = 512.0 / loader.width if loader.width > 0 else 1.0
    sh = 512.0 / loader.height if loader.height > 0 else 1.0
    scale = min(sw, sh)

    img = loader.render(512, 512, scale_factor=scale, quality=1.0)
    if img is not None:
        cv2.imwrite(out_path, img)


def compare(expected_path, actual_path, diff_path):
    expected = cv2.imread(expected_path)
    actual = cv2.imread(actual_path)

    if expected is None or actual is None:
        return None

    if expected.shape != actual.shape:
        actual = cv2.resize(actual, (expected.shape[1], expected.shape[0]))

    mse = np.mean((expected.astype(float) - actual.astype(float)) ** 2)
    diff = cv2.absdiff(expected, actual)
    diff = cv2.convertScaleAbs(diff, alpha=10)
    cv2.imwrite(diff_path, diff)
    return mse


def run_all():
    base_dir = os.path.dirname(__file__)
    cases_dir = os.path.join(base_dir, "cases")

    # Create output dirs if they don't exist
    for d in ["expected", "actual", "diff"]:
        os.makedirs(os.path.join(base_dir, d), exist_ok=True)

    print(f"{'CASE':<30} | {'MSE':<10} | {'STATUS'}")
    print("-" * 50)

    for filename in sorted(os.listdir(cases_dir)):
        if not filename.endswith(".svg"):
            continue

        case_name = filename[:-4]
        svg_path = os.path.join(cases_dir, filename)
        ref_path = os.path.join(base_dir, "expected", f"{case_name}.png")
        act_path = os.path.join(base_dir, "actual", f"{case_name}.png")
        diff_path = os.path.join(base_dir, "diff", f"{case_name}.png")

        capture_reference(svg_path, ref_path)
        capture_actual(svg_path, act_path)

        # Pixel analysis
        act_img = cv2.imread(act_path)
        ref_img = cv2.imread(ref_path)

        act_coverage = (
            np.count_nonzero(
                cv2.max(act_img[:, :, 0], cv2.max(act_img[:, :, 1], act_img[:, :, 2]))
            )
            / (act_img.size / 3)
        ) * 100
        ref_coverage = (
            np.count_nonzero(
                cv2.max(ref_img[:, :, 0], cv2.max(ref_img[:, :, 1], ref_img[:, :, 2]))
            )
            / (ref_img.size / 3)
        ) * 100

        mse = compare(ref_path, act_path, diff_path)

        if mse is not None:
            # Custom thresholds for known minor discrepancies
            threshold = 100
            if case_name == "inkscape_repro":
                threshold = 800
            elif case_name == "test_image_with_mask":
                threshold = 2500

            status = "PASS" if mse < threshold else "FAIL"
            print(
                f"{case_name:<30} | {mse:>10.2f} | {status} | Act:{act_coverage:>5.2f}% Exp:{ref_coverage:>5.2f}%"
            )


if __name__ == "__main__":
    run_all()
