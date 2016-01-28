"""
- image.py -

Module to handle WPP and SW4 images of Maps or Cross-Sections

By: Omri Volk & Shahar Shani-Kadmiel, June 2015, kadmiel@post.bgu.ac.il

"""
import os

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable

from seispy.plotting.dic_and_dtype import (
    SW4_header_dtype, SW4_patch_dtype, SW4_plane_dict, SW4_mode_dict, prec_dict)
from seispy.plotting import set_matplotlib_rc_params


set_matplotlib_rc_params()


class Image(object):
    """
    A class to hold WPP or SW4 image files
    """

    def __init__(self):
        self.filename          = None
        self.number_of_patches = 1 # or more
        self.precision         = 4 # or 8
        self.type              = 'cross-section' # or or 'map'
        self.mode              = None # velmag, ux, uy, uz, etc.
        self.unit              = None # m, m/s, kg/cm^3, etc.
        self.cycle             = 0
        self.time              = 0
        self.plane             = 'X' # or Y or Z
        self.min               = 0
        self.max               = 0
        self.std               = 0
        self.rms               = 0

        self.patches = []

    def _readSW4hdr(self, f):
        """
        Read SW4 header information and store it in an Image object
        """

        header = np.fromfile(f, SW4_header_dtype, 1)[0]
        (self.precision,
         self.number_of_patches,
         self.time,
         self._plane,
         self.coordinate,
         self.mode,
         self.gridinfo,
         self.creation_time) = header

    def _readSW4patches(self, f):
        """
        Read SW4 patch data and store it in a list of Patch objects
        under Image.patches
        """
        patch_info = np.fromfile(f,SW4_patch_dtype,self.number_of_patches)
        for i,item in enumerate(patch_info):
            patch = Patch()
            patch.number = i
            (patch.h,
             patch.zmin,
             patch.ib,
             patch.ni,
             patch.jb,
             patch.nj) = item
            data = np.fromfile(f, self.precision, patch.ni*patch.nj)
            patch.data = data.reshape(patch.nj, patch.ni)

            if self._plane in (0, 1):
                patch.extent = (
                    0 - (patch.h / 2.0),
                    (patch.ni - 1) * patch.h + (patch.h / 2.0),
                    patch.zmin - (patch.h / 2.0),
                    patch.zmin + (patch.nj - 1) * patch.h + (patch.h / 2.0))
            elif self._plane == 2:
                patch.data = patch.data.T
                patch.extent = (
                    0 - (patch.h / 2.0),
                    (patch.nj - 1) * patch.h + (patch.h / 2.0),
                    0 - (patch.h / 2.0),
                    (patch.ni - 1) * patch.h + (patch.h / 2.0))
            patch.min    = data.min()
            patch.max    = data.max()
            patch.std    = data.std()
            patch.rms    = np.sqrt(np.mean(data**2))
            self.patches.append(patch)


class Patch(object):
    """
    A class to hold WPP or SW4 patch data
    """

    def __init__(self):
        self.number       = 0
        self.h            = 0
        self.zmin         = 1
        self.ib           = 1
        self.ni           = 0
        self.jb           = 1
        self.nj           = 0
        self.extent       = (0,1,0,1)
        self.data         = None
        self.min          = 0
        self.max          = 0
        self.std          = 0
        self.rms          = 0

    def plot(self, ax=None, vmin='min', vmax='max', colorbar=True,
             **kwargs):

        if ax is None:
            fig, ax = plt.subplots()

        ax.set_aspect(1)

        if vmax is 'max':
            vmax = self.max
        elif type(vmax) is str:
            try:
                factor = float(vmax)
                vmax = factor*self.rms
                if self.min < 0:
                    vmin = -vmax

            except ValueError:
                print ('Warning! keyword vmax=$s in not understood...\n' %vmax,
                       'Setting to max')
                vmax = self.max

        if vmin is 'min':
            vmin = self.min

        if vmin > self.min and vmax < self.max:
            extend = 'both'
        elif vmin == self.min and vmax == self.max:
            extend = 'neither'
        elif vmin > self.min:
            extend = 'min'
        else:# vmax < self.max:
            extend = 'max'

        print vmin, vmax
        im = ax.imshow(self.data, extent=self.extent, vmin=vmin, vmax=vmax,
                       origin="lower", interpolation="nearest", **kwargs)
        if colorbar:
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="3%", pad=0.1)
            cb = plt.colorbar(im, cax=cax,
                              extend=extend,
                              label=colorbar if type(colorbar) is str else '')
        else:
            cb = None

        try:
            return fig, ax, cb
        except NameError:
            return cb


def read(filename='random', verbose=False):
    """
    Read image data, cross-section or map into a SeisPy Image object.

    Params:
    --------

    filename : if no filename is passed, by default, a random image is generated
        if filename is None, an empty Image object is returned.

    verbose : if True, print some information while reading the file.

    Returns:
    ---------

    an Image object with a list of Patch objects
    """
    image = Image()
    image.filename = filename

    if filename is 'random': # generate random data and populate the objects
        patch = Patch()

        ni,nj = 100,200
        h = 100.
        zmin = 0
        data = 2*(np.random.rand(ni,nj)-0.5)

        patch.data   = data
        patch.ni     = ni
        patch.nj     = nj
        patch.number = 0
        patch.h      = h
        patch.zmin   = zmin
        patch.extent = (0,nj*h,zmin+ni*h,zmin)
        patch.min    = data.min()
        patch.max    = data.max()
        patch.std    = data.std()
        patch.rms    = np.sqrt(np.mean(data**2))

        image.patches += [patch]
    elif filename is None:
        pass
    else:
        (name, image.cycle, plane,
         coordinate, mode, is_SW4) = parse_filename(filename)

        if is_SW4:
            with open(image.filename,'rb') as f:
                image._readSW4hdr(f)
                image.precision = prec_dict[image.precision]
                image.plane = SW4_plane_dict[image.plane]
                image.mode, image.unit = SW4_mode_dict[image.mode]
                image._readSW4patches(f)
    return image


def parse_filename(filename):
    """ This function parses the filename in order to figure out its type.

    Parameters
    -----------
    filename : string

    Returns
    --------
    name, cycle, plane, coordinate, mode, is_SW4

    """

    basename = os.path.basename(filename)
    name, extention = os.path.splitext(basename)
    if extention == '.sw4img':
        name, cycle, plane, mode = name.rsplit('.',3)
        cycle = int(cycle.split('=')[-1])
        plane, coordinate = plane.split('=')
        return name, cycle, plane, coordinate, mode, True
    else:
        name, cycle, plane, mode = basename.rsplit('.',3)
        cycle = int(cycle.split('=')[-1])
        plane, coordinate = plane.split('=')
        return name, cycle, plane, coordinate, mode, False