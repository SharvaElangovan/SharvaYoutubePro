"""Create differences in images for Spot the Difference puzzles."""

import random
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import copy


class DifferenceMaker:
    """Create subtle differences in images."""

    def __init__(self):
        self.min_region_size = 50
        self.max_region_size = 150

    def _get_random_region(self, width, height, size=None):
        """Get a random region that fits within the image."""
        if size is None:
            size = random.randint(self.min_region_size, self.max_region_size)

        # Keep away from edges
        margin = 50
        x = random.randint(margin, width - size - margin)
        y = random.randint(margin, height - size - margin)

        return (x, y, x + size, y + size)

    def color_shift(self, img, region=None):
        """Shift color of a region (hue rotation)."""
        img = img.copy()
        width, height = img.size

        if region is None:
            region = self._get_random_region(width, height)

        # Extract region
        cropped = img.crop(region)

        # Shift hue by converting to HSV-like manipulation
        r, g, b = cropped.split()
        # Swap channels for a visible color shift
        shifted = Image.merge('RGB', (b, r, g))

        img.paste(shifted, region[:2])
        return img, region, "color_shift"

    def remove_object(self, img, region=None):
        """Remove object by filling with nearby pixels (clone stamp effect)."""
        img = img.copy()
        width, height = img.size

        if region is None:
            region = self._get_random_region(width, height, size=80)

        x1, y1, x2, y2 = region
        size = x2 - x1

        # Get pixels from nearby area (offset to the right or left)
        offset = size + 20
        if x1 + offset + size < width:
            source_region = (x1 + offset, y1, x2 + offset, y2)
        else:
            source_region = (x1 - offset, y1, x2 - offset, y2)

        try:
            source = img.crop(source_region)
            img.paste(source, (x1, y1))
        except:
            # Fallback: blur the region
            cropped = img.crop(region)
            blurred = cropped.filter(ImageFilter.GaussianBlur(radius=10))
            img.paste(blurred, region[:2])

        return img, region, "remove_object"

    def add_shape(self, img, region=None):
        """Add a small shape to the image."""
        img = img.copy()
        width, height = img.size
        draw = ImageDraw.Draw(img)

        if region is None:
            size = random.randint(30, 60)
            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)
            region = (x, y, x + size, y + size)

        # Random color
        color = (
            random.randint(100, 255),
            random.randint(100, 255),
            random.randint(100, 255)
        )

        # Random shape
        shape_type = random.choice(['ellipse', 'rectangle'])
        if shape_type == 'ellipse':
            draw.ellipse(region, fill=color)
        else:
            draw.rectangle(region, fill=color)

        return img, region, "add_shape"

    def mirror_region(self, img, region=None):
        """Mirror/flip a region horizontally."""
        img = img.copy()
        width, height = img.size

        if region is None:
            region = self._get_random_region(width, height, size=100)

        cropped = img.crop(region)
        flipped = cropped.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        img.paste(flipped, region[:2])

        return img, region, "mirror_region"

    def brightness_change(self, img, region=None):
        """Change brightness of a region."""
        img = img.copy()
        width, height = img.size

        if region is None:
            region = self._get_random_region(width, height, size=120)

        cropped = img.crop(region)
        enhancer = ImageEnhance.Brightness(cropped)
        # Make noticeably brighter or darker
        factor = random.choice([0.5, 1.5])
        enhanced = enhancer.enhance(factor)
        img.paste(enhanced, region[:2])

        return img, region, "brightness_change"

    def blur_region(self, img, region=None):
        """Blur a region of the image."""
        img = img.copy()
        width, height = img.size

        if region is None:
            region = self._get_random_region(width, height, size=100)

        cropped = img.crop(region)
        blurred = cropped.filter(ImageFilter.GaussianBlur(radius=5))
        img.paste(blurred, region[:2])

        return img, region, "blur_region"

    def shift_region(self, img, region=None):
        """Shift a region slightly (object moved)."""
        img = img.copy()
        width, height = img.size

        if region is None:
            region = self._get_random_region(width, height, size=80)

        x1, y1, x2, y2 = region
        cropped = img.crop(region)

        # Fill original with nearby pixels
        offset_x = 30
        if x1 + (x2 - x1) + offset_x * 2 < width:
            fill_region = (x1 + offset_x, y1, x2 + offset_x, y2)
        else:
            fill_region = (x1 - offset_x, y1, x2 - offset_x, y2)

        try:
            fill = img.crop(fill_region)
            img.paste(fill, (x1, y1))
        except:
            pass

        # Paste cropped at new position
        new_x = x1 + random.choice([-20, 20])
        new_y = y1 + random.choice([-20, 20])
        new_x = max(0, min(new_x, width - (x2 - x1)))
        new_y = max(0, min(new_y, height - (y2 - y1)))
        img.paste(cropped, (new_x, new_y))

        return img, (new_x, new_y, new_x + (x2-x1), new_y + (y2-y1)), "shift_region"

    def create_differences(self, original_img, num_differences=3):
        """
        Create a modified image with specified number of differences.

        Returns:
            modified_img: The image with differences
            differences: List of (region, type) tuples describing each difference
        """
        modified = original_img.copy()
        differences = []

        # Available modification functions
        modifications = [
            self.color_shift,
            self.remove_object,
            self.add_shape,
            self.mirror_region,
            self.brightness_change,
            self.blur_region,
            self.shift_region,
        ]

        # Apply random modifications
        used_regions = []
        attempts = 0
        max_attempts = num_differences * 3

        while len(differences) < num_differences and attempts < max_attempts:
            attempts += 1

            # Pick random modification
            mod_func = random.choice(modifications)

            # Apply it
            try:
                modified, region, mod_type = mod_func(modified)

                # Check for overlap with existing regions
                overlap = False
                for used in used_regions:
                    if self._regions_overlap(region, used):
                        overlap = True
                        break

                if not overlap:
                    differences.append({
                        'region': region,
                        'type': mod_type,
                        'center': ((region[0] + region[2]) // 2, (region[1] + region[3]) // 2)
                    })
                    used_regions.append(region)
            except Exception as e:
                print(f"Modification failed: {e}")
                continue

        return modified, differences

    def _regions_overlap(self, r1, r2, margin=50):
        """Check if two regions overlap (with margin)."""
        x1_1, y1_1, x2_1, y2_1 = r1
        x1_2, y1_2, x2_2, y2_2 = r2

        # Add margin
        x1_1 -= margin
        y1_1 -= margin
        x2_1 += margin
        y2_1 += margin

        return not (x2_1 < x1_2 or x2_2 < x1_1 or y2_1 < y1_2 or y2_2 < y1_1)


# Test
if __name__ == "__main__":
    # Create a test image
    img = Image.new('RGB', (1920, 1080), (100, 150, 200))
    draw = ImageDraw.Draw(img)

    # Add some shapes to test with
    for i in range(20):
        x = random.randint(100, 1800)
        y = random.randint(100, 980)
        color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        draw.ellipse((x, y, x+50, y+50), fill=color)

    maker = DifferenceMaker()
    modified, diffs = maker.create_differences(img, num_differences=5)

    print(f"Created {len(diffs)} differences:")
    for d in diffs:
        print(f"  - {d['type']} at {d['center']}")

    img.save("test_original.jpg")
    modified.save("test_modified.jpg")
    print("Saved test_original.jpg and test_modified.jpg")
