'''Character segmentation and extraction from character sheet'''

import os
import cv2 as cv
import numpy as np
from skimage import morphology as morph

class CharacterSheetExtractor(object):

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

    def extract_characters(self, in_file, out_dir, pad_factor, j_thres, s_thres, min_size, shade_overlap):
        '''Extract individual character and write to individual file'''
        print ('Segmenting characters / objects and extract to individual image...')
        try:
            # Reading input image
            img = cv.imread(in_file, 1)
        except Exception as e:
            print (f'{e}: Failure on reading input file. Verify input path and file name.')      
            return   
        # Create contours
        cts = self.get_contours(img, j_thres, s_thres)
        # Get contour with area larger than 100 pixel square. The smaller one considered noise
        _, lcts = self.get_large_contours(cts, min_size)
        # Tell the number of bounding boxes
        print (f'Objects found: {len(lcts)}')
        # Create bounding boxes
        bboxes = self.create_bboxes(lcts)
        # Creating output files
        try:
            # Creating output sub dir
            in_file_name = os.path.splitext(os.path.split(in_file)[-1])[0]
            sub_dir = os.path.join(out_dir, in_file_name)
            os.makedirs(sub_dir, exist_ok=True)
        except Exception as e:
            print (f'{e}: Failure on creating output directory.')      
            return   
        i = 0
        for bbox in bboxes:
            print (f'Writing file {i+1} from {len(bboxes)}')
            x1, x2, y1, y2 = self.get_bbox_points(bbox, img.shape, pad_factor)
            # Creating character image patch
            char =  img[y1:y2, x1:x2,::]
            if shade_overlap:
                char = self.shade_overlap(char)
            # Writing to file
            cv.imwrite(f'{sub_dir}/char{i}.png', char)
            i+=1
        print (f'Output files written to {sub_dir}/')
        return True

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

    def segment_characters(self, in_file, out_dir, j_thres, s_thres, min_size, create_bbox, bbox_color, bbox_line_width, create_blend):
        '''Create binary mask image based on character segmentation'''
        try:
            img = cv.imread(in_file, 1)
        except Exception as e:
            print (f'{e}: Failure on reading input file. Verify input path and file name')      
            return

        print ('Creating segmentation mask image...')
        # Create contours
        cts = self.get_contours(img, j_thres, s_thres)
        # Get contour with area larger than 100 pixel square. The smaller one considered noise
        _, lcts = self.get_large_contours(cts, min_size)
        # Tell the number of bounding boxes
        print (f'Objects found: {len(lcts)}')
        # Create zero mask
        mask = np.zeros(img.shape[0:2])
        for lct in lcts:
        # Creating solid polygon
            mask = cv.fillPoly(mask, [lct], 255)
        # Writing to file
        out_file_name =  os.path.splitext(os.path.split(in_file)[-1])[0]
        target_path = os.path.join(out_dir, f'{out_file_name}_mask.png')
        cv.imwrite(target_path, mask)
        print (f'Segmentation mask image created as {target_path}')

        if create_bbox:
            # --bbox options active. Create bounding box embedded image.
            img_bbox = self.draw_bboxes(img, lcts, bbox_color, bbox_line_width)
            # Writing to file
            out_file_name =  os.path.splitext(os.path.split(in_file)[-1])[0]
            target_path = os.path.join(out_dir, f'{out_file_name}_bbox.png')
            cv.imwrite(target_path, img_bbox)
            print (f'Bounding box image created as {target_path}')

        if create_blend:
            # --blend options active. Create image with segmentation mask blending
            img_blended = self.create_blend(img, mask)
            # Writing to file
            out_file_name =  os.path.splitext(os.path.split(in_file)[-1])[0]
            target_path = os.path.join(out_dir, f'{out_file_name}_blend.png')
            cv.imwrite(target_path, img_blended)
            print (f'Blend image created as {target_path}')
