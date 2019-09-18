# AFM Bacteria Identification

[![N|Solid](https://cldup.com/dTxpPi9lDf.thumb.png)](https://nodesource.com/products/nsolid)

[![Build Status](https://travis-ci.org/joemccann/dillinger.svg?branch=master)](https://travis-ci.org/joemccann/dillinger)

This project is build to work with a neaSNOM Microscope ([neaspec GmbH](https://www.neaspec.com/), Germany), but should be easily expandable to work with other Device for [Atomic Force Microscopy (AFM)](https://en.wikipedia.org/wiki/Atomic_force_microscopy) as well. At the moment the Software uses the SDKs provided by neaspec to control the Microscope.
It is based on the [OpenCV](https://opencv.org/) Library and uses [Canny Edge Detection](https://en.wikipedia.org/wiki/Canny_edge_detector) as well as OpenCVs [findContours()](https://opencv-python-tutroals.readthedocs.io/en/latest/py_tutorials/py_imgproc/py_contours/py_table_of_contents_contours/py_table_of_contents_contours.html) Function.

# Basic Algorithm

Assuming you have two twodimensional Data Arrays representing two Measurement Directions that differ by 180° the Algorithms works like this (Code is in Python 3.6): 

https://raw.githubusercontent.com/AFMHZB/AFM/AFMHZB-pictures/Pre_Fix.png

<img src="https://raw.githubusercontent.com/AFMHZB/AFM/AFMHZB-pictures/Pre_Fix.png" alt="Alt Text" width="40%">

First both Arrays are leveld using linear regression. The function looks like this:
```sh
def plane_correction(raw):
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
```

![alt text](https://raw.githubusercontent.com/AFMHZB/AFM/AFMHZB-pictures/forward.png) ![alt text](https://raw.githubusercontent.com/AFMHZB/AFM/AFMHZB-pictures/backward.png)

As you can see in the Pictures it is possible for the Data to have "Tails". To Correct them both Matrices are Stacked to 1D Arrays and then combined to one single Array using the smaller value of the two. 
```sh
#z_data is left to right tip direction, r_data is right to left
comb_data = np.array([np.ndarray.flatten(z_data), np.ndarray.flatten(r_data)])
#self._shape saves the shape of the input Array
data = np.reshape(np.nanmin(comb_data, axis=0), self._shape)
```
