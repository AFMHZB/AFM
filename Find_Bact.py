import cv2
import numpy as np
import copy

class FindBacteria:
    
    def __init__(self, z_data, r_data, bac_params, ratio):
        self._dict = {}
        self._z_data = z_data
        self._r_data = r_data
        self._shape = self._z_data.shape
        #Parameter to define a bacteria, usually as tuple of (min, max)
        self._length = bac_params['length']#tuple
        self._width = bac_params['width']#tuple
        self._height = bac_params['height']#tuple
        self._corona = int(bac_params['corona'] / ratio)#single value
        self._limit = bac_params['climit']#single value
        self._ratio = ratio
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        print(exc_type, exc_val, exc_tb)
        return
    
    def get_dict(self):
        return copy.deepcopy(self._dict)
    
    def auto_canny(self, image, sigma=0.5):
        v = np.median(image)
        lower = int(max(0, (1.0 - sigma) * v))
        upper = int(min(255, (1.0 + sigma) * v))
        edged = cv2.Canny(image, lower, upper)
        return edged
    
    def set_data(self, z_data, r_data):
        self._z_data = z_data
        self._r_data = r_data
        self._shape = self._z_data.shape
    
    def plane_correction(self, raw):
        null_val = np.average(raw)
        raw[np.isnan(raw)] = null_val
        m = raw.shape
        X1, X2 = np.mgrid[:m[0], :m[1]]
        X = np.hstack((np.reshape(X1, (m[0]*m[1], 1)), np.reshape(X2, (m[0]*m[1], 1))))
        X = np.hstack((np.ones((m[0]*m[1], 1)), X))
        YY = np.reshape(raw, (m[0]*m[1], 1))
        theta = np.dot(np.dot(np.linalg.pinv(np.dot(X.transpose(), X)), X.transpose()), YY)
        plane = np.reshape(np.dot(X, theta), m)
        return (raw - plane)
    
    def data_correction(self, limit):
        z_data = self.plane_correction(self._z_data)
        r_data = self.plane_correction(self._r_data)
        comb_data = np.array([np.ndarray.flatten(z_data), np.ndarray.flatten(r_data)])
        data = np.reshape(np.nanmin(comb_data, axis=0), self._shape)
        data = self.plane_correction(data)
        for x in range(len(data)):
            data[x] = data[x] - np.median(data[x] - data[x-1])
        data = data - np.nanmin(data)
        top = np.nanmax(data)
        data[np.where(data > limit)] = limit
        return data, top
    
    def find_bacteria(self, data, top):
        norm = cv2.normalize(data,None,0,255,cv2.NORM_MINMAX , cv2.CV_8U)
        img = cv2.bilateralFilter(norm.copy(),10,50,50, cv2.BORDER_WRAP)
        _,thresh = cv2.threshold(img,100,255,cv2.THRESH_BINARY)
        canny = self.auto_canny(thresh)
        contours, _ = cv2.findContours(canny, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        contours = [cv2.convexHull(x) for x in contours]
        self._dict['Contours_IMG'] = cv2.drawContours(norm.copy(), contours, -1, 255, 2)
        
        bacteria = []
        
        for c in contours:
            (_,_),size,angle = cv2.minAreaRect(c)
            angle = 90 + angle if size[1] > size[0] else 180 + angle
            angle = np.deg2rad(angle)
            width = min(size) * self._ratio
            length = max(size) * self._ratio
            if self._width[0] <= width <= self._width[1] and self._length[0] <= length <= self._length[1]:
                mask = np.zeros(self._shape, np.uint8)
                cv2.drawContours(mask, [c], 0, 1, -1)
                h_upper = np.nanmax(data[np.where(mask==1)])
                if self._height[0] * 10**(-6) <= h_upper <= self._height[1] * 10**(-6):
                    bacteria.append( (c, angle) )
                    
        self._dict['Bacteria_IMG'] = cv2.drawContours(norm.copy(), [x[0] for x in bacteria], -1, 255, 2)
        if len(bacteria) > 0:
            bac_found = True
            counter = 0
            self._dict['Bacteria'] = {}
            for bact in bacteria:
                M = cv2.moments(bact[0])
                cx = int(M['m10']/M['m00'])
                cy = int(M['m01']/M['m00'])
                counter += 1
                bact_name = 'Bacteria{}'.format(counter)
                self._dict['Bacteria'][bact_name] = {}
                _, radius = cv2.minEnclosingCircle(bact[0])
                
                vect_x = np.cos(bact[1]) * (radius / 2)
                vect_y = np.sin(bact[1]) * (radius / 2)
                
                top_x = int(cx + vect_x)
                top_y = int(cy + vect_y)
                bot_x = int(cx - vect_x)
                bot_y = int(cy - vect_y)
                
                self._dict['Bacteria'][bact_name]['Points'] = {}
                self._dict['Bacteria'][bact_name]['Points']['Center'] = {}
                self._dict['Bacteria'][bact_name]['Points']['Top'] = {}
                self._dict['Bacteria'][bact_name]['Points']['Bot'] = {}
                self._dict['Bacteria'][bact_name]['Points']['Reference'] = {}
                self._dict['Bacteria'][bact_name]['Points']['Center']['Coord'] = (cx, cy)
                self._dict['Bacteria'][bact_name]['Points']['Top']['Coord'] = (top_x, top_y)
                self._dict['Bacteria'][bact_name]['Points']['Bot']['Coord'] = (bot_x, bot_y)
                
                new_res = 2.5 * radius
                new_res = new_res if new_res < self._shape[0] / 2 else self._shape[0] / 2
                box_x = cx - new_res
                box_y = cy - new_res
                
                width = int(2 * new_res) if box_x + (2 * new_res) <= self._shape[0] else int(self._shape[0] - abs(box_x))
                height = int(2 * new_res) if box_y + (2 * new_res) <= self._shape[1] else int(self._shape[1] - abs(box_y))
                #must be done last, or the rect will just be moved
                box_x = int(box_x) if box_x > 0 else 0
                box_y = int(box_y) if box_y > 0 else 0
                
                x1 = box_x + self._corona
                x2 = box_x + width - self._corona
                y1 = box_y + self._corona
                y2 = box_y + height - self._corona
                data_sqr = data.copy()[y1:y2, x1:x2]
                ref_mask = np.zeros(data_sqr.shape)
                references = []
                (mask_x, mask_y) = np.where(data_sqr < self._limit * top)
                ref_mask[(mask_x, mask_y)] = 1
                for x,y in zip(mask_x, mask_y):
                    YY, XX = np.ogrid[-x : data_sqr.shape[0]-x, -y : data_sqr.shape[1]-y]
                    mask = XX * XX + YY * YY <= self._corona * self._corona
                    if all(ref_mask[mask]):
                        references.append((y + x1, x + y1))
                if len(references) > 0:
                    references.sort(key=lambda x: cv2.pointPolygonTest(bact[0], (x[0], x[1]), True), reverse=True)
                    self._dict['Bacteria'][bact_name]['Points']['Reference']['Coord'] = references[0]
                    data_sqr_img = cv2.normalize(norm.copy(),None,0,255,cv2.NORM_MINMAX , cv2.CV_8U)
                    for key in self._dict['Bacteria'][bact_name]['Points'].keys():
                        cv2.circle(data_sqr_img, self._dict['Bacteria'][bact_name]['Points'][key]['Coord'], 3, 255, -1)
                    #cv2.circle(data_sqr_img, references[0], 3, 255, -1)
                    self._dict['Bacteria'][bact_name]['dxy'] = new_res * self._ratio
                    self._dict['Bacteria'][bact_name]['pxy'] = new_res * 2
                    self._dict['Bacteria'][bact_name]['Meassurement_Points_IMG'] = data_sqr_img
        else:
            bac_found = False
        return bac_found
                    
