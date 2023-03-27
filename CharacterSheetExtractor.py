'''Character segmentation and extraction from character sheet'''

import os
import cv2 as cv
import numpy as np
from skimage import morphology as morph
import hashlib
import json


class CharacterSheetExtractor(object):

    def __init__(self) -> None:
        # File hash generator object
        self.hasher = hashlib.sha256()


    def get_contours(self, img, j_thres, s_thres):
        '''Create contours based on edge detection and morphological operations'''
        # Create grayscale version
        img_gray = cv.cvtColor(img.copy(), cv.COLOR_BGR2GRAY)
        # Noise removal
        img_gray = cv.GaussianBlur(img_gray, (7,7), 0)
        # Edge detection
        edge = cv.Canny(img_gray, 30, 70)
        # Dilate for getting sure foreground (object) area
        edge = cv.dilate(edge, np.ones((j_thres,j_thres)), 1)
        # Closing black holes inside the object with area < 10000 square pixels
        edge = morph.area_closing(edge, 10000)
        # Try to separate touching objects
        edge = cv.erode(edge, np.ones((s_thres,s_thres)), 1)
        # Find contour
        cts,_ = cv.findContours(edge.astype('uint8'), cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
        return cts


    def get_large_contours(self, cts, size):
        '''Return contouts larger than size'''
        area = []
        large_contour = []
        for ct in cts:
            a = cv.contourArea(ct)
            if a > size:
                area.append(a)
                large_contour.append(ct)
        return area, large_contour


    def create_bboxes(self, contours):
        '''Create oject bounding boxes from contours'''
        bboxes = []
        for ct in contours:    
            x,y,w,h = cv.boundingRect(ct)
            bboxes.append([x,y,w,h])
        return bboxes


    def get_bbox_points(self, bbox, img_shape, pad_factor=0):
        '''Return bounding box corner points'''
        x, y, w, h = bbox
        # Padding
        y1 = y - int(h*pad_factor)
        y2 = y + h + int(h*pad_factor)
        x1 = x - int(w*pad_factor)
        x2 = x + w + int(w*pad_factor)
        # Limiting
        if y1 < 0:
            y1 = 0
        if y2 > img_shape[0]-1:
            y2 = img_shape[0]-1
        if x1 < 0:
            x1 = 0
        if x2 > img_shape[1]-1:
            x2 = img_shape[1]-1
        return x1, x2, y1, y2


    def draw_bboxes(self, img, contours, line_color, line_width):
        '''Create sheet images with object bounding boxes'''

        print ('Creating bounding boxes embedded image...')
        # Creating rectangles to bound objects
        bboxes = self.create_bboxes(contours)
        # Create a copy for drawing bboxes
        img_bbox = img.copy()
        # Writing to file
        i = 1
        for bbox in bboxes:
            #print (f'Drawing box {i} from {len(bboxes)}')
            x1, x2, y1, y2 = self.get_bbox_points(bbox, img_bbox.shape)
            cv.rectangle(img_bbox,(x1,y1),(x2,y2), line_color, line_width)
            i+=1

        return img_bbox
           
            
    def create_blend(self, img, binary_mask):
        '''Create image with segmentation mask blending'''
        print ('Creating mask-blended image...')
        blend_mask = np.zeros(img.shape).astype('uint8')
        it = np.nditer (binary_mask, flags = ['multi_index'])
        for x in it:
            if (x==255):
                # Create a blue mask
                blend_mask[it.multi_index[0], it.multi_index[1],:] = [255,102,0]
        img_blended = cv.addWeighted(img, 0.5, blend_mask, 0.5,0)
        return img_blended


    def shade_overlap(self, img_patch):
        '''Try to remove overlap leftover with white pixels'''
        # Create gray version of patch
        gray = cv.cvtColor(img_patch.copy(), cv.COLOR_BGR2GRAY) 
        # Noise removal
        gray = cv.GaussianBlur(gray, (3,3), 0)
        # Edge detection
        edge = cv.Canny(gray, 30, 70)
        # Heavy dilate
        mask_fg = cv.dilate(edge, np.ones((5,5)), 1)
        # Find contour
        cts,_ = cv.findContours(mask_fg.astype('uint8'), cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
        # Get contour with area larger than 100 pixel square. The smaller one considered noise
        area, lcts = self.get_large_contours(cts, 300)
        # Largest contour
        largest = lcts[np.argmax(area)]
        # Create mask
        mask_largest = np.zeros(mask_fg.shape)
        # Creating solid polygon
        mask_largest = cv.fillPoly(mask_largest, [largest], 255)
        # Create blank white patch
        new_img_patch = np.ones(img_patch.shape)*255
        # Create new patch based on mask
        # Alter blank white patch with original image patch according to 255 value on mask
        it = np.nditer (mask_largest, flags = ['multi_index'])
        for x in it:
            if (x==255):
                new_img_patch[it.multi_index[0], it.multi_index[1],:] = img_patch[it.multi_index[0], it.multi_index[1],:]
        return new_img_patch


    def compute_hash(self, file_path):
        '''Compute hash for image in given file_path'''
        with open(file_path, 'rb') as img_file:
            img_bytes = img_file.read()
        self.hasher.update(img_bytes)
        hash_id = self.hasher.hexdigest()
        return hash_id


    def save_to_json_file(self, out_json, output_path): 
        '''Saving to JSON file'''
        # Serializing json
        json_object = json.dumps(out_json, indent=4)    
        # Writing to output folder
        with open(output_path, "a") as outfile:
            outfile.write(json_object)
            outfile.write('\n')


    def extract_characters(self, input_path, out_dir, pad_factor, j_thres, s_thres, min_size, shade_overlap):
        '''Extract individual character and write to individual file'''
        
        # Placeholder for file paths
        files = []

        # Make a list of input file paths and prepare sub directory for writing output files
        if os.path.isfile(input_path):
            # A single file. Add the path to the list
            files.append(input_path)
            # Creating output sub dir based on input file name
            input_file_name = os.path.splitext(os.path.split(input_path)[-1])[0]
            sub_dir = os.path.join(out_dir, input_file_name)
            os.makedirs(sub_dir, exist_ok=True)

        else:
            # It is a directory. Add path of all files to the list
            for _root, _, _files in os.walk(input_path):
                for _file in _files:
                    files.append(os.path.join(_root, _file))
            # Creating output sub dir based on input file name
            input_dir_name = os.path.split(os.path.dirname(f'{input_path}/'))[-1]
            sub_dir = os.path.join(out_dir, input_dir_name)
            os.makedirs(sub_dir, exist_ok=True)

        print ('Segmenting characters / objects and extract to individual image...')

        for file in files:  
            
            try:
                img = cv.imread(file, 1)
            except Exception as e:
                print (f'{e}: Failure on reading image file. Could be unsupported / invalid image file')      
                continue

            # Compute file hash
            hash_id = self.compute_hash(file)

            # Create contours
            cts = self.get_contours(img, j_thres, s_thres)
            # Get contour with area larger than 100 pixel square. The smaller one considered noise
            _, lcts = self.get_large_contours(cts, min_size)
            # Tell the number of bounding boxes
            print (f'Objects found: {len(lcts)}')
            # Create bounding boxes
            bboxes = self.create_bboxes(lcts)
            
            i = 0
            for bbox in bboxes:
                print (f'Processing object {i+1} from {len(bboxes)}')
                x1, x2, y1, y2 = self.get_bbox_points(bbox, img.shape, pad_factor)
                # Creating character image patch
                char =  img[y1:y2, x1:x2,::]
                if shade_overlap:
                    char = self.shade_overlap(char)

                # Writing to file
                if not os.path.isfile(input_path):
                    # Input path is directory. So create a sub-sub directory to contain segmentation result from each image
                    sub_sub_dir = os.path.join(sub_dir, os.path.splitext(os.path.split(file)[-1])[0])
                    os.makedirs(sub_sub_dir, exist_ok=True)
                    # Write the file in sub-sub directory
                    file_name = f'{sub_sub_dir}/object_{i}.png'
                    print(file_name)
                    cv.imwrite(file_name, char)
                else:
                    # Input path is a single file. So Write the file in sub directory
                    file_name = f'{sub_dir}/object_{i}.png'
                    print (file_name)
                    cv.imwrite(file_name, char)
                i+=1
                

            # Creating dictionary for all bboxes
            bbox_dicts = []
            for bbox in bboxes:
                # Get x, y, w, h of each box
                x, y, w, h = bbox
                bbox_dicts.append({'width':w, 'height':h, 'origin_x':x, 'origin_y':y, 'center_x':x+int(w/2), 'center_y':y+int(h/2)})

            # Creating output JSON
            out_json = {'hash':hash_id, 'file_name':file, 'img_size':(img.shape[1], img.shape[0]), 'n_bbox':len(lcts), 'bboxes':bbox_dicts}
            # Saving to output JSON file
            self.save_to_json_file(out_json, output_path = f'{sub_dir}/output.json')


    def segment_characters(self, input_path, out_dir, j_thres, s_thres, min_size, create_bbox, bbox_color, bbox_line_width, create_blend):
        
        # Placeholder for file paths
        files = []

        # Make a list of input file paths and prepare sub directory for writing output files
        if os.path.isfile(input_path):
            # A single file. Add the path to the list
            files.append(input_path)
            # Creating output sub dir based on input file name
            input_file_name = os.path.splitext(os.path.split(input_path)[-1])[0]
            sub_dir = os.path.join(out_dir, input_file_name)
            os.makedirs(sub_dir, exist_ok=True)

        else:
            # It is a directory. Add path of all files to the list
            for _root, _, _files in os.walk(input_path):
                for _file in _files:
                    files.append(os.path.join(_root, _file))
            # Creating output sub dir based on input file name
            input_dir_name = os.path.split(os.path.dirname(f'{input_path}/'))[-1]
            sub_dir = os.path.join(out_dir, input_dir_name)
            os.makedirs(sub_dir, exist_ok=True)
            

        for file in files:

            '''Create binary mask image based on character segmentation'''
            try:
                img = cv.imread(file, 1)
            except Exception as e:
                print (f'{e}: Failure on reading image file. Could be unsupported / invalid image file')      
                continue
            
            # Compute file hash
            hash_id = self.compute_hash(file)

            # Create segmentation mask image
            print ('Creating segmentation mask image...')
            # Get contours
            cts = self.get_contours(img, j_thres, s_thres)
            # Get contour with area larger than 100 pixel square. The smaller one considered noise
            _, lcts = self.get_large_contours(cts, min_size)
            # Tell the number of bounding boxes
            print (f'Objects found: {len(lcts)}')
            # Create bounding boxes and get the coordinates
            bboxes = self.create_bboxes(lcts)
            # Create zero mask
            mask = np.zeros(img.shape[0:2])
            for lct in lcts:
            # Creating solid polygon
                mask = cv.fillPoly(mask, [lct], 255)

            # Writing to file
            out_file_name =  f'{os.path.splitext(os.path.split(file)[-1])[0]}_mask.png'
            out_file_path = os.path.join(sub_dir, out_file_name)
            cv.imwrite(out_file_path, mask)
            print (f'Segmentation mask image created as {out_file_path}')

            if create_bbox:
                # --bbox options active. Create bounding box embedded image.
                img_bbox = self.draw_bboxes(img, lcts, bbox_color, bbox_line_width)
                # Writing to file
                out_file_name =  f'{os.path.splitext(os.path.split(file)[-1])[0]}_bbox.png'
                out_file_path = os.path.join(sub_dir, out_file_name)
                cv.imwrite(out_file_path, img_bbox)
                print (f'Bounding box image created as {out_file_path}')

            if create_blend:
                # --blend options active. Create image with segmentation mask blending
                img_blended = self.create_blend(img, mask)
                # Writing to file
                out_file_name =  f'{os.path.splitext(os.path.split(file)[-1])[0]}_blend.png'
                out_file_path = os.path.join(sub_dir, out_file_name)
                cv.imwrite(out_file_path, img_blended)
                print (f'Blend image created as {out_file_path}')

            # Creating dictionary for all bboxes
            bbox_dicts = []
            for bbox in bboxes:
                # Get x, y, w, h of each box
                x, y, w, h = bbox
                bbox_dicts.append({'width':w, 'height':h, 'origin_x':x, 'origin_y':y, 'center_x':x+int(w/2), 'center_y':y+int(h/2)})

            # Creating output JSON
            out_json = {'hash':hash_id, 'file_name':file, 'img_size':(img.shape[1], img.shape[0]), 'n_bbox':len(lcts), 'bboxes':bbox_dicts}
            # Saving to output JSON file
            out_file_name = 'output.json'
            out_file_path = os.path.join(sub_dir, out_file_name)
            self.save_to_json_file(out_json, output_path = out_file_path)


