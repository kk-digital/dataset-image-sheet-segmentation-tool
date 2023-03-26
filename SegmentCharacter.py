import argparse
import time
from CharacterSheetExtractor import CharacterSheetExtractor as Extractor

# Argument handling
parser = argparse.ArgumentParser()
parser.add_argument('--input_path', type = str, required=True)
parser.add_argument('--out_dir', default = 'output/', type = str)
parser.add_argument('--pad_factor', default = 0.1, type = float)
parser.add_argument('--j_thres', default = 3, type = int)
parser.add_argument('--s_thres', default = 7, type = int)
parser.add_argument('--min_size', default = 500, type = int)
parser.add_argument('--bbox', action=argparse.BooleanOptionalAction)
parser.add_argument('--blend', action=argparse.BooleanOptionalAction)
args = parser.parse_args()

# Path to input file
input_path = args.input_path
# Output directory
out_dir = args.out_dir
# Padding factor for output image (0-1.0)
pad_factor = args.pad_factor
if pad_factor < 0:
    pad_factor = 0
    print ('Invalid pad_factor (use 0 - 1.0). Pad factor set to 0.')
elif pad_factor > 1.0:
    pad_factor = 1.0
    print ('Invalid pad_factor (use 0 - 1.0). Pad factor set to 1.0')
# Join threshold for adjusting the integration level of individual object.
j_thres = args.j_thres
if j_thres < 3:
    j_thres = 3
    print ('Invalid j_thres (use 0 - 15). j_thres set to 0')
elif j_thres > 15:
    j_thres = 15
    print ('Invalid j_thres (use 0 - 15). j_thres set to 15')
# Separation threshold for adjusting the separation level of neighboring objects.
s_thres = args.s_thres
if s_thres < 3:
    s_thres = 3
    print ('Invalid s_thres (use 0 - 15). s_thres set to 0')
elif s_thres > 15:
    s_thres = 15
    print ('Invalid s_thres (use 0 - 15). s_thres set to 15')
# Minimum size in square pixels for characters to be detected
min_size = args.min_size
# Create image with bounding boxes
create_bbox = args.bbox
bbox_color = (0,255,0) # Green
bbox_line_width = 5
# Create image with segmentation mask blending
create_blend = args.blend

# Start time
t1 = time.time()
# Extractor object
extractor = Extractor()
# Individual character extraction and writing to individual file
extractor.segment_characters(input_path, out_dir, j_thres, s_thres, min_size, create_bbox, bbox_color, bbox_line_width, create_blend)
# End time
t2 = time.time()

print (f'Time elapsed {round((t2-t1),2)}s')



