# -*- coding: utf-8 -*-
"""Offscreen VTK render of the fixed sh_cans:top mesh, GUI-style shading."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from _gap_cache import load_top

import vtk
from vtkmodules.vtkInteractionStyle import *  # noqa

def build_actor(mesh, color=(0.55, 0.58, 0.62)):
    pts = np.asarray(mesh["points"], float)
    vp = vtk.vtkPoints()
    for p in pts:
        vp.InsertNextPoint(float(p[0]), float(p[1]), float(p[2]))
    polys = vtk.vtkCellArray()
    for f in mesh["faces"]:
        polys.InsertNextCell(3)
        for vi in f:
            polys.InsertCellPoint(int(vi))
    pd = vtk.vtkPolyData()
    pd.SetPoints(vp)
    pd.SetPolys(polys)
    mp = vtk.vtkPolyDataMapper()
    mp.SetInputData(pd)
    actor = vtk.vtkActor()
    actor.SetMapper(mp)
    prop = actor.GetProperty()
    prop.SetColor(*color)
    prop.SetAmbientColor(*color)
    prop.SetDiffuseColor(*color)
    prop.SetInterpolationToFlat()
    prop.BackfaceCullingOn()      # match GUI: back faces culled
    prop.SetAmbient(0.78)
    prop.SetDiffuse(0.24)
    prop.SetSpecular(0.0)
    return actor

def build_feature_edges(mesh, color=(0.14, 0.15, 0.17)):
    """Only silhouette/feature edges (not full triangulation)."""
    pts = np.asarray(mesh["points"], float)
    vp = vtk.vtkPoints()
    for p in pts:
        vp.InsertNextPoint(float(p[0]), float(p[1]), float(p[2]))
    polys = vtk.vtkCellArray()
    for f in mesh["faces"]:
        polys.InsertNextCell(3)
        for vi in f:
            polys.InsertCellPoint(int(vi))
    pd = vtk.vtkPolyData()
    pd.SetPoints(vp)
    pd.SetPolys(polys)
    fe = vtk.vtkFeatureEdges()
    fe.SetInputData(pd)
    fe.BoundaryEdgesOn()
    fe.FeatureEdgesOn()
    fe.ManifoldEdgesOff()
    fe.NonManifoldEdgesOff()
    fe.ColoringOff()
    fe.SetFeatureAngle(48.0)
    fe.Update()
    mp = vtk.vtkPolyDataMapper()
    mp.SetInputConnection(fe.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mp)
    prop = actor.GetProperty()
    prop.SetColor(*color)
    prop.SetLineWidth(1.4)
    prop.SetRepresentationToWireframe()
    try:
        prop.SetLineSmoothing(True)
    except Exception:
        pass
    try:
        prop.LightingOff()
    except Exception:
        pass
    return actor

def render(mesh, az, el, path, size=(1000, 700), zoom=1.0, with_edges=True):
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.80, 0.85, 0.89)
    ren.SetBackground2(0.52, 0.62, 0.72)
    ren.GradientBackgroundOn()
    ren.TwoSidedLightingOn()
    ren.SetAutomaticLightCreation(0)
    ren.UseFXAAOn()
    ren.AddActor(build_actor(mesh))
    if with_edges:
        ren.AddActor(build_feature_edges(mesh))
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetMultiSamples(8)
    win.AddRenderer(ren)
    win.SetSize(*size)
    ren.ResetCamera()
    cam = ren.GetActiveCamera()
    cam.Azimuth(az)
    cam.Elevation(el)
    cam.Zoom(zoom)
    ren.ResetCameraClippingRange()
    win.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.Update()
    wr = vtk.vtkPNGWriter()
    wr.SetInputConnection(w2i.GetOutputPort())
    wr.SetFileName(path)
    wr.Write()
    print("wrote", path)

m = load_top()["top"]["mesh"]
# View A: top-oblique (like user's red-circle screenshot), feature edges
render(m, az=25, el=40, path="_top_viewA.png", zoom=1.4, with_edges=True)
# View B: front-side low (like the CST comparison), feature edges
render(m, az=-35, el=-12, path="_top_viewB.png", zoom=1.4, with_edges=True)
# View C: no edges, pure shaded
render(m, az=25, el=40, path="_top_viewA_noedge.png", zoom=1.4, with_edges=False)
