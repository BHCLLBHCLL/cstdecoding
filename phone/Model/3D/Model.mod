'# MWS Version: Version 2024.0 - Aug 01 2023 - ACIS 33.0.1 -

'# length = mm
'# frequency = GHz
'# time = ns
'# frequency range: fmin = 0 fmax = 30
'# created = '[VERSION]2022.0|31.0.1|20210625[/VERSION]


'@ use template: Antenna - 5G mmWave.cfg

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
'set the units
With Units
    .Geometry "mm"
    .Frequency "GHz"
    .Voltage "V"
    .Resistance "Ohm"
    .Inductance "H"
    .TemperatureUnit  "Kelvin"
    .Time "ns"
    .Current "A"
    .Conductance "Siemens"
    .Capacitance "F"
End With

'----------------------------------------------------------------------------

'set the frequency range
Solver.FrequencyRange "0", "30"

'----------------------------------------------------------------------------

Plot.DrawBox True

With Background
     .Type "Normal"
     .Epsilon "1.0"
     .Mu "1.0"
     .XminSpace "0.0"
     .XmaxSpace "0.0"
     .YminSpace "0.0"
     .YmaxSpace "0.0"
     .ZminSpace "0.0"
     .ZmaxSpace "0.0"
End With

With Boundary
     .Xmin "expanded open"
     .Xmax "expanded open"
     .Ymin "expanded open"
     .Ymax "expanded open"
     .Zmin "expanded open"
     .Zmax "expanded open"
     .Xsymmetry "none"
     .Ysymmetry "none"
     .Zsymmetry "none"
End With

Group.Add "AntennaMetals", "mesh"
Group.Add "AntennaPorts", "mesh"
Group.Add "NoRefinement", "mesh"
MakeSureParameterExists "antenna_metal_thickness", "0.01"
SetParameterDescription "antenna_metal_thickness", "antenna element metal thickness"
MakeSureParameterExists "antenna_port_width", "0.1"
SetParameterDescription "antenna_port_width", "antenna port width"
MakeSureParameterExists "max_frequency", "32.0"
SetParameterDescription "max_frequency", "maximum frequency (GHz)"
MakeSureParameterExists "step_size_ports", "antenna_port_width/3"
SetParameterDescription "step_size_ports", "cell size applied to AntennaPorts mesh group"
MakeSureParameterExists "max_cell_size", "1000*2.997e8/(max_frequency*1e9*15)"
SetParameterDescription "max_cell_size", "maximum cell size"
MakeSureParameterExists "edge_ratio", "1+int(max_cell_size/antenna_metal_thickness)"
SetParameterDescription "edge_ratio", "edge refinement ratio for AntennaMetals mesh group"

With Mesh
     .MergeThinPECLayerFixpoints "True"
     .RatioLimit "20"
     .FPBAAvoidNonRegUnite "True"
     .ConsiderSpaceForLowerMeshLimit "False"
     .MinimumStepNumber "5"
     .AutoMeshNumberOfShapeFaces "300"
     .SetGenericUserFlag("AllowPowerLossPP", True)
End With

' ### FIT Hex Mesh Settings #############################################################
With MeshSettings
     .SetMeshType "Hex"
     .Set "RatioLimitGeometry", "20"
End With

With MeshSettings
     With .ItemMeshSettings ("group$AntennaPorts")
          .SetMeshType "Hex"
          .Set "Step", "step_size_ports", "step_size_ports", "step_size_ports"
     End With
     With .ItemMeshSettings ("group$AntennaMetals")
          .SetMeshType "Hex"
          .Set "UseEdgeRefinement", 1
          .Set "EdgeRefinement", "16"
     End With
End With

' ### TLM Hex Mesh Settings #############################################################

With MeshSettings
     .SetMeshType "HexTLM"

     .Set "SnapToSpheres", "0"
     .Set "SnapToEllipses", "0"

   ' =====================================================
   ' below settings will be global defaults in v2021-SP1, then no longer needed here
     .Set "Equilibrate", "1.5"
     .Set "BufferLinesNear", "3"
     .Set "FaceRefinementNSteps", "2"
     .Set "EllipseRefinementNSteps", "2"
     .Set "FaceRefinementBufferLines", "3"

     .Set "LimitCellSizeType", "Maxcellsizeneartomodel"
     .Set "UseCellSizeSmoothingRatio", "1"
     .Set "CellSizeSmoothingRatio", "4"
     .Set "LimitCellConnects", "1"
     .Set "UnlumpEdges", "1"
   ' =====================================================
End With

With MeshSettings
     With .ItemMeshSettings ("group$AntennaPorts")
          .SetMeshType "HexTLM"
          .Set "Step", "step_size_ports", "step_size_ports", "step_size_ports"
     End With
     With .ItemMeshSettings ("group$AntennaMetals")
          .SetMeshType "HexTLM"
          .Set "UseEdgeRefinement", 1
          .Set "EdgeRefinement", "edge_ratio"
     End With
     With .ItemMeshSettings ("group$NoRefinement")
       .SetMeshType "HexTLM"
       .Set "UseForRefinement", 1
       .Set "StepRefinementCollectPolicy", "REFINE_NONE"
       .Set "UseDielectrics", 0
       .Set "UseEdgeRefinement", 0
       .Set "UseForSnapping", 0
       .Set "UseSnappingPriority", "0"
       .Set "UseVolumeRefinement", 0
     End With
End With

Resulttree.UpdateTree
ExpandTreeItems ("Groups")
ExpandTreeItems ("Groups\Mesh Groups")

With Solver
     .Method "Hexahedral TLM"
     .SteadyStateLimit "no check"
End With

'STEADY STATE
With Solver
     .SteadyStateDurationType "Time"
     .NumberOfPulseWidths "20"
     .SteadyStateDurationTime "10" ' nsec  GetTimeUnit
     .SteadyStateDurationTimeAsDistance "2837.48"
     .StopCriteriaShowExcitation "False"
     .RemoveAllStopCriteria
     .AddStopCriterion "All S-Parameters", "0.004", "1", "False"
     .AddStopCriterion "Transmission S-Parameters", "0.004", "1", "False"
     .AddStopCriterion "Reflection S-Parameters", "0.001", "2", "True"
     .AddStopCriterion "All Probes", "0.004", "1", "False"
     .AddStopCriterion "All Radiated Powers", "0.001", "2", "True"
End With

'HEXAHEDRAL TLM
With Solver
     .UseAbsorbingBoundary "False"
End With

' change mesh adaption scheme to energy
' 		(planar structures tend to store high energy
'     	 locally at edges rather than globally in volume)
MeshAdaption3D.SetAdaptionStrategy "Energy"

' switch on FD-TET setting for accurate farfields
FDSolver.ExtrudeOpenBC "True"

Solver.PrepareFarfields "False"

'----------------------------------------------------------------------------

With Solver
     .Method "Hexahedral TLM"
End With

With Mesh
     .MeshType "HexahedralTLM"
     .SetCreator "High Frequency"
End With

'set the solver type
ChangeSolverType("HF Time Domain")

'----------------------------------------------------------------------------


'----------------------------------------------------------------------------

'preserve project units
With Units 
     .Geometry "mm" 
     .Frequency "GHz" 
     .Time "ns" 
     .TemperatureUnit "Kelvin" 
     .Voltage "V" 
     .Current "A" 
     .Resistance "Ohm" 
     .Conductance "Siemens" 
     .Capacitance "PikoF" 
     .Inductance "NanoH" 
     .SetResultUnit "frequency", "frequency", "" 
End With

'@ import sat/sab file: E:\CSTphone2022.sab

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With SAT
     .Reset 
     .FileName "*CSTphone2022.sab" 
     .Id "1" 
     .Version "9.0" 
     .ScaleToUnit "0" 
     .ImportToActiveCoordinateSystem "True" 
     .Curves "True" 
     .Read 
End With

'@ define material: Phone/Aluminum

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
With Material
     .Reset
     .Name "Aluminum"
     .Folder "Phone"
     .FrqType "static"
     .Type "Normal"
     .SetMaterialUnit "Hz", "mm"
     .Epsilon "1"
     .Mu "1.0"
     .Kappa "3.56e+007"
     .TanD "0.0"
     .TanDFreq "0.0"
     .TanDGiven "False"
     .TanDModel "ConstTanD"
     .KappaM "0"
     .TanDM "0.0"
     .TanDMFreq "0.0"
     .TanDMGiven "False"
     .TanDMModel "ConstTanD"
     .DispModelEps "None"
     .DispModelMu "None"
     .DispersiveFittingSchemeEps "General 1st"
     .DispersiveFittingSchemeMu "General 1st"
     .UseGeneralDispersionEps "False"
     .UseGeneralDispersionMu "False"
     .FrqType "all"
     .Type "Lossy metal"
     .MaterialUnit "Frequency", "GHz"
     .MaterialUnit "Geometry", "mm"
     .MaterialUnit "Time", "s"
     .MaterialUnit "Temperature", "Kelvin"
     .Mu "1.0"
     .Sigma "3.56e+007"
     .Rho "2700.0"
     .ThermalType "Normal"
     .ThermalConductivity "237.0"
     .SpecificHeat "900", "J/K/kg"
     .MetabolicRate "0"
     .BloodFlow "0"
     .VoxelConvection "0"
     .MechanicsType "Isotropic"
     .YoungsModulus "69"
     .PoissonsRatio "0.33"
     .ThermalExpansionRate "23"
     .ReferenceCoordSystem "Global"
     .CoordSystemType "Cartesian"
     .NLAnisotropy "False"
     .NLAStackingFactor "1"
     .NLADirectionX "1"
     .NLADirectionY "0"
     .NLADirectionZ "0"
     .Colour "0.752941", "0.752941", "0.752941" 
     .Wireframe "False"
     .Reflection "False"
     .Allowoutline "True"
     .Transparentoutline "False"
     .Transparency "0"
     .Create
End With

'@ define material: Phone/Battery_Shell

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
With Material 
     .Reset 
     .Name "Battery_Shell"
     .Folder "Phone"
     .Rho "0.0"
     .ThermalType "Normal"
     .ThermalConductivity "0"
     .SpecificHeat "0", "J/K/kg"
     .DynamicViscosity "0"
     .Emissivity "0"
     .MetabolicRate "0.0"
     .VoxelConvection "0.0"
     .BloodFlow "0"
     .MechanicsType "Unused"
     .IntrinsicCarrierDensity "0"
     .FrqType "all"
     .Type "Normal"
     .MaterialUnit "Frequency", "GHz"
     .MaterialUnit "Geometry", "mm"
     .MaterialUnit "Time", "s"
     .Epsilon "1.5"
     .Mu "1"
     .Sigma "0"
     .TanD "0.0"
     .TanDFreq "0.0"
     .TanDGiven "False"
     .TanDModel "ConstTanD"
     .SetConstTanDStrategyEps "AutomaticOrder"
     .ConstTanDModelOrderEps "3"
     .DjordjevicSarkarUpperFreqEps "0"
     .SetElParametricConductivity "False"
     .ReferenceCoordSystem "Global"
     .CoordSystemType "Cartesian"
     .SigmaM "0"
     .TanDM "0.0"
     .TanDMFreq "0.0"
     .TanDMGiven "False"
     .TanDMModel "ConstTanD"
     .SetConstTanDStrategyMu "AutomaticOrder"
     .ConstTanDModelOrderMu "3"
     .DjordjevicSarkarUpperFreqMu "0"
     .SetMagParametricConductivity "False"
     .DispModelEps  "None"
     .DispModelMu "None"
     .DispersiveFittingSchemeEps "Nth Order"
     .MaximalOrderNthModelFitEps "10"
     .ErrorLimitNthModelFitEps "0.1"
     .UseOnlyDataInSimFreqRangeNthModelEps "False"
     .DispersiveFittingSchemeMu "Nth Order"
     .MaximalOrderNthModelFitMu "10"
     .ErrorLimitNthModelFitMu "0.1"
     .UseOnlyDataInSimFreqRangeNthModelMu "False"
     .UseGeneralDispersionEps "False"
     .UseGeneralDispersionMu "False"
     .NLAnisotropy "False"
     .NLAStackingFactor "1"
     .NLADirectionX "1"
     .NLADirectionY "0"
     .NLADirectionZ "0"
     .LatticeScattering "Electron", "0.1", "0."
     .LatticeScattering "Hole", "0.1", "0."
     .EffectiveMassForConductivity "Electron", "0.25"
     .EffectiveMassForConductivity "Hole", "0.35"
     .Colour "0", "0.501961", "0.752941" 
     .Wireframe "False" 
     .Reflection "False" 
     .Allowoutline "True" 
     .Transparentoutline "False" 
     .Transparency "0" 
     .Create
End With

'@ define material: Phone/Copper (annealed)

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
With Material
     .Reset
     .Name "Copper (annealed)"
     .Folder "Phone"
     .FrqType "static"
     .Type "Normal"
     .SetMaterialUnit "Hz", "mm"
     .Epsilon "1"
     .Mu "1.0"
     .Kappa "5.8e+007"
     .TanD "0.0"
     .TanDFreq "0.0"
     .TanDGiven "False"
     .TanDModel "ConstTanD"
     .KappaM "0"
     .TanDM "0.0"
     .TanDMFreq "0.0"
     .TanDMGiven "False"
     .TanDMModel "ConstTanD"
     .DispModelEps "None"
     .DispModelMu "None"
     .DispersiveFittingSchemeEps "Nth Order"
     .DispersiveFittingSchemeMu "Nth Order"
     .UseGeneralDispersionEps "False"
     .UseGeneralDispersionMu "False"
     .FrqType "all"
     .Type "Lossy metal"
     .SetMaterialUnit "GHz", "mm"
     .Mu "1.0"
     .Kappa "5.8e+007"
     .Rho "8930.0"
     .ThermalType "Normal"
     .ThermalConductivity "401.0"
     .SpecificHeat "390", "J/K/kg"
     .MetabolicRate "0"
     .BloodFlow "0"
     .VoxelConvection "0"
     .MechanicsType "Isotropic"
     .YoungsModulus "120"
     .PoissonsRatio "0.33"
     .ThermalExpansionRate "17"
     .Colour "1", "1", "0"
     .Wireframe "False"
     .Reflection "False"
     .Allowoutline "True"
     .Transparentoutline "False"
     .Transparency "0"
     .Create
End With

'@ define material: Phone/Fused Silica

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
With Material 
     .Reset 
     .Name "Fused Silica"
     .Folder "Phone"
     .Rho "0.0"
     .ThermalType "Normal"
     .ThermalConductivity "0"
     .SpecificHeat "0", "J/K/kg"
     .DynamicViscosity "0"
     .Emissivity "0"
     .MetabolicRate "0.0"
     .VoxelConvection "0.0"
     .BloodFlow "0"
     .MechanicsType "Unused"
     .IntrinsicCarrierDensity "0"
     .FrqType "all"
     .Type "Normal"
     .MaterialUnit "Frequency", "GHz"
     .MaterialUnit "Geometry", "mm"
     .MaterialUnit "Time", "s"
     .Epsilon "3.8"
     .Mu "1"
     .Sigma "0"
     .TanD "0.0"
     .TanDFreq "0.0"
     .TanDGiven "False"
     .TanDModel "ConstTanD"
     .SetConstTanDStrategyEps "AutomaticOrder"
     .ConstTanDModelOrderEps "3"
     .DjordjevicSarkarUpperFreqEps "0"
     .SetElParametricConductivity "False"
     .ReferenceCoordSystem "Global"
     .CoordSystemType "Cartesian"
     .SigmaM "0"
     .TanDM "0.0"
     .TanDMFreq "0.0"
     .TanDMGiven "False"
     .TanDMModel "ConstTanD"
     .SetConstTanDStrategyMu "AutomaticOrder"
     .ConstTanDModelOrderMu "3"
     .DjordjevicSarkarUpperFreqMu "0"
     .SetMagParametricConductivity "False"
     .DispModelEps  "None"
     .DispModelMu "None"
     .DispersiveFittingSchemeEps "Nth Order"
     .MaximalOrderNthModelFitEps "10"
     .ErrorLimitNthModelFitEps "0.1"
     .UseOnlyDataInSimFreqRangeNthModelEps "False"
     .DispersiveFittingSchemeMu "Nth Order"
     .MaximalOrderNthModelFitMu "10"
     .ErrorLimitNthModelFitMu "0.1"
     .UseOnlyDataInSimFreqRangeNthModelMu "False"
     .UseGeneralDispersionEps "False"
     .UseGeneralDispersionMu "False"
     .NLAnisotropy "False"
     .NLAStackingFactor "1"
     .NLADirectionX "1"
     .NLADirectionY "0"
     .NLADirectionZ "0"
     .LatticeScattering "Electron", "0.1", "0."
     .LatticeScattering "Hole", "0.1", "0."
     .EffectiveMassForConductivity "Electron", "0.25"
     .EffectiveMassForConductivity "Hole", "0.35"
     .Colour "0", "0.501961", "0" 
     .Wireframe "False" 
     .Reflection "False" 
     .Allowoutline "True" 
     .Transparentoutline "False" 
     .Transparency "0" 
     .Create
End With

'@ define material: Phone/Glass

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
With Material 
     .Reset 
     .Name "Glass"
     .Folder "Phone"
     .Rho "0.0"
     .ThermalType "Normal"
     .ThermalConductivity "0"
     .SpecificHeat "0", "J/K/kg"
     .DynamicViscosity "0"
     .Emissivity "0"
     .MetabolicRate "0.0"
     .VoxelConvection "0.0"
     .BloodFlow "0"
     .MechanicsType "Unused"
     .IntrinsicCarrierDensity "0"
     .FrqType "all"
     .Type "Normal"
     .MaterialUnit "Frequency", "GHz"
     .MaterialUnit "Geometry", "mm"
     .MaterialUnit "Time", "s"
     .Epsilon "4.82"
     .Mu "1"
     .Sigma "0"
     .TanD "0.0"
     .TanDFreq "0.0"
     .TanDGiven "False"
     .TanDModel "ConstTanD"
     .SetConstTanDStrategyEps "AutomaticOrder"
     .ConstTanDModelOrderEps "3"
     .DjordjevicSarkarUpperFreqEps "0"
     .SetElParametricConductivity "False"
     .ReferenceCoordSystem "Global"
     .CoordSystemType "Cartesian"
     .SigmaM "0"
     .TanDM "0.0"
     .TanDMFreq "0.0"
     .TanDMGiven "False"
     .TanDMModel "ConstTanD"
     .SetConstTanDStrategyMu "AutomaticOrder"
     .ConstTanDModelOrderMu "3"
     .DjordjevicSarkarUpperFreqMu "0"
     .SetMagParametricConductivity "False"
     .DispModelEps  "None"
     .DispModelMu "None"
     .DispersiveFittingSchemeEps "Nth Order"
     .MaximalOrderNthModelFitEps "10"
     .ErrorLimitNthModelFitEps "0.1"
     .UseOnlyDataInSimFreqRangeNthModelEps "False"
     .DispersiveFittingSchemeMu "Nth Order"
     .MaximalOrderNthModelFitMu "10"
     .ErrorLimitNthModelFitMu "0.1"
     .UseOnlyDataInSimFreqRangeNthModelMu "False"
     .UseGeneralDispersionEps "False"
     .UseGeneralDispersionMu "False"
     .NLAnisotropy "False"
     .NLAStackingFactor "1"
     .NLADirectionX "1"
     .NLADirectionY "0"
     .NLADirectionZ "0"
     .LatticeScattering "Electron", "0.1", "0."
     .LatticeScattering "Hole", "0.1", "0."
     .EffectiveMassForConductivity "Electron", "0.25"
     .EffectiveMassForConductivity "Hole", "0.35"
     .Colour "0.501961", "0", "0.501961" 
     .Wireframe "False" 
     .Reflection "False" 
     .Allowoutline "True" 
     .Transparentoutline "False" 
     .Transparency "0" 
     .Create
End With

'@ define material: Phone/Plastic

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
With Material 
     .Reset 
     .Name "Plastic"
     .Folder "Phone"
     .Rho "0.0"
     .ThermalType "Normal"
     .ThermalConductivity "0"
     .SpecificHeat "0", "J/K/kg"
     .DynamicViscosity "0"
     .Emissivity "0"
     .MetabolicRate "0.0"
     .VoxelConvection "0.0"
     .BloodFlow "0"
     .MechanicsType "Unused"
     .IntrinsicCarrierDensity "0"
     .FrqType "all"
     .Type "Normal"
     .MaterialUnit "Frequency", "GHz"
     .MaterialUnit "Geometry", "mm"
     .MaterialUnit "Time", "s"
     .Epsilon "2.2"
     .Mu "1"
     .Sigma "0"
     .TanD "0.0"
     .TanDFreq "0.0"
     .TanDGiven "False"
     .TanDModel "ConstTanD"
     .SetConstTanDStrategyEps "AutomaticOrder"
     .ConstTanDModelOrderEps "3"
     .DjordjevicSarkarUpperFreqEps "0"
     .SetElParametricConductivity "False"
     .ReferenceCoordSystem "Global"
     .CoordSystemType "Cartesian"
     .SigmaM "0"
     .TanDM "0.0"
     .TanDMFreq "0.0"
     .TanDMGiven "False"
     .TanDMModel "ConstTanD"
     .SetConstTanDStrategyMu "AutomaticOrder"
     .ConstTanDModelOrderMu "3"
     .DjordjevicSarkarUpperFreqMu "0"
     .SetMagParametricConductivity "False"
     .DispModelEps  "None"
     .DispModelMu "None"
     .DispersiveFittingSchemeEps "Nth Order"
     .MaximalOrderNthModelFitEps "10"
     .ErrorLimitNthModelFitEps "0.1"
     .UseOnlyDataInSimFreqRangeNthModelEps "False"
     .DispersiveFittingSchemeMu "Nth Order"
     .MaximalOrderNthModelFitMu "10"
     .ErrorLimitNthModelFitMu "0.1"
     .UseOnlyDataInSimFreqRangeNthModelMu "False"
     .UseGeneralDispersionEps "False"
     .UseGeneralDispersionMu "False"
     .NLAnisotropy "False"
     .NLAStackingFactor "1"
     .NLADirectionX "1"
     .NLADirectionY "0"
     .NLADirectionZ "0"
     .LatticeScattering "Electron", "0.1", "0."
     .LatticeScattering "Hole", "0.1", "0."
     .EffectiveMassForConductivity "Electron", "0.25"
     .EffectiveMassForConductivity "Hole", "0.35"
     .Colour "0.501961", "0.501961", "0.501961" 
     .Wireframe "False" 
     .Reflection "False" 
     .Allowoutline "True" 
     .Transparentoutline "False" 
     .Transparency "0" 
     .Create
End With

'@ define material: Phone/Plastic_HDPE

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
With Material 
     .Reset 
     .Name "Plastic_HDPE"
     .Folder "Phone"
     .Rho "0.0"
     .ThermalType "Normal"
     .ThermalConductivity "0"
     .SpecificHeat "0", "J/K/kg"
     .DynamicViscosity "0"
     .Emissivity "0"
     .MetabolicRate "0.0"
     .VoxelConvection "0.0"
     .BloodFlow "0"
     .MechanicsType "Unused"
     .IntrinsicCarrierDensity "0"
     .FrqType "all"
     .Type "Normal"
     .MaterialUnit "Frequency", "GHz"
     .MaterialUnit "Geometry", "mm"
     .MaterialUnit "Time", "s"
     .Epsilon "2.3"
     .Mu "1"
     .Sigma "0"
     .TanD "0.0"
     .TanDFreq "0.0"
     .TanDGiven "False"
     .TanDModel "ConstTanD"
     .SetConstTanDStrategyEps "AutomaticOrder"
     .ConstTanDModelOrderEps "3"
     .DjordjevicSarkarUpperFreqEps "0"
     .SetElParametricConductivity "False"
     .ReferenceCoordSystem "Global"
     .CoordSystemType "Cartesian"
     .SigmaM "0"
     .TanDM "0.0"
     .TanDMFreq "0.0"
     .TanDMGiven "False"
     .TanDMModel "ConstTanD"
     .SetConstTanDStrategyMu "AutomaticOrder"
     .ConstTanDModelOrderMu "3"
     .DjordjevicSarkarUpperFreqMu "0"
     .SetMagParametricConductivity "False"
     .DispModelEps  "None"
     .DispModelMu "None"
     .DispersiveFittingSchemeEps "Nth Order"
     .MaximalOrderNthModelFitEps "10"
     .ErrorLimitNthModelFitEps "0.1"
     .UseOnlyDataInSimFreqRangeNthModelEps "False"
     .DispersiveFittingSchemeMu "Nth Order"
     .MaximalOrderNthModelFitMu "10"
     .ErrorLimitNthModelFitMu "0.1"
     .UseOnlyDataInSimFreqRangeNthModelMu "False"
     .UseGeneralDispersionEps "False"
     .UseGeneralDispersionMu "False"
     .NLAnisotropy "False"
     .NLAStackingFactor "1"
     .NLADirectionX "1"
     .NLADirectionY "0"
     .NLADirectionZ "0"
     .LatticeScattering "Electron", "0.1", "0."
     .LatticeScattering "Hole", "0.1", "0."
     .EffectiveMassForConductivity "Electron", "0.25"
     .EffectiveMassForConductivity "Hole", "0.35"
     .Colour "0.623529", "1", "0.623529" 
     .Wireframe "False" 
     .Reflection "False" 
     .Allowoutline "True" 
     .Transparentoutline "False" 
     .Transparency "0" 
     .Create
End With

'@ define material: Phone/PTFE (loss free)

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
With Material 
     .Reset 
     .Name "PTFE (loss free)"
     .Folder "Phone"
     .Rho "0.0"
     .ThermalType "Normal"
     .ThermalConductivity "0"
     .SpecificHeat "0", "J/K/kg"
     .DynamicViscosity "0"
     .Emissivity "0"
     .MetabolicRate "0.0"
     .VoxelConvection "0.0"
     .BloodFlow "0"
     .MechanicsType "Unused"
     .IntrinsicCarrierDensity "0"
     .FrqType "all"
     .Type "Normal"
     .MaterialUnit "Frequency", "GHz"
     .MaterialUnit "Geometry", "mm"
     .MaterialUnit "Time", "s"
     .Epsilon "2.1"
     .Mu "1"
     .Sigma "0"
     .TanD "0.0"
     .TanDFreq "0.0"
     .TanDGiven "False"
     .TanDModel "ConstTanD"
     .SetConstTanDStrategyEps "AutomaticOrder"
     .ConstTanDModelOrderEps "3"
     .DjordjevicSarkarUpperFreqEps "0"
     .SetElParametricConductivity "False"
     .ReferenceCoordSystem "Global"
     .CoordSystemType "Cartesian"
     .SigmaM "0"
     .TanDM "0.0"
     .TanDMFreq "0.0"
     .TanDMGiven "False"
     .TanDMModel "ConstTanD"
     .SetConstTanDStrategyMu "AutomaticOrder"
     .ConstTanDModelOrderMu "3"
     .DjordjevicSarkarUpperFreqMu "0"
     .SetMagParametricConductivity "False"
     .DispModelEps  "None"
     .DispModelMu "None"
     .DispersiveFittingSchemeEps "Nth Order"
     .MaximalOrderNthModelFitEps "10"
     .ErrorLimitNthModelFitEps "0.1"
     .UseOnlyDataInSimFreqRangeNthModelEps "False"
     .DispersiveFittingSchemeMu "Nth Order"
     .MaximalOrderNthModelFitMu "10"
     .ErrorLimitNthModelFitMu "0.1"
     .UseOnlyDataInSimFreqRangeNthModelMu "False"
     .UseGeneralDispersionEps "False"
     .UseGeneralDispersionMu "False"
     .NLAnisotropy "False"
     .NLAStackingFactor "1"
     .NLADirectionX "1"
     .NLADirectionY "0"
     .NLADirectionZ "0"
     .LatticeScattering "Electron", "0.1", "0."
     .LatticeScattering "Hole", "0.1", "0."
     .EffectiveMassForConductivity "Electron", "0.25"
     .EffectiveMassForConductivity "Hole", "0.35"
     .Colour "0.75", "0.95", "0.85" 
     .Wireframe "False" 
     .Reflection "False" 
     .Allowoutline "True" 
     .Transparentoutline "False" 
     .Transparency "0" 
     .Create
End With

'@ define material: Phone/PlasticCover

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With Material 
     .Reset 
     .Name "PlasticCover"
     .Folder "Phone"
     .Rho "0.0"
     .ThermalType "Normal"
     .ThermalConductivity "0"
     .SpecificHeat "0", "J/K/kg"
     .DynamicViscosity "0"
     .Emissivity "0"
     .MetabolicRate "0.0"
     .VoxelConvection "0.0"
     .BloodFlow "0"
     .MechanicsType "Unused"
     .IntrinsicCarrierDensity "0"
     .FrqType "all"
     .Type "Normal"
     .MaterialUnit "Frequency", "GHz"
     .MaterialUnit "Geometry", "mm"
     .MaterialUnit "Time", "s"
     .Epsilon "2.1"
     .Mu "1.0"
     .Sigma "0"
     .TanD "0.0"
     .TanDFreq "0.0"
     .TanDGiven "False"
     .TanDModel "ConstTanD"
     .SetConstTanDStrategyEps "AutomaticOrder"
     .ConstTanDModelOrderEps "3"
     .DjordjevicSarkarUpperFreqEps "0"
     .SetElParametricConductivity "False"
     .ReferenceCoordSystem "Global"
     .CoordSystemType "Cartesian"
     .SigmaM "0"
     .TanDM "0.0"
     .TanDMFreq "0.0"
     .TanDMGiven "False"
     .TanDMModel "ConstTanD"
     .SetConstTanDStrategyMu "AutomaticOrder"
     .ConstTanDModelOrderMu "3"
     .DjordjevicSarkarUpperFreqMu "0"
     .SetMagParametricConductivity "False"
     .DispModelEps  "None"
     .DispModelMu "None"
     .DispersiveFittingSchemeEps "Nth Order"
     .MaximalOrderNthModelFitEps "10"
     .ErrorLimitNthModelFitEps "0.1"
     .UseOnlyDataInSimFreqRangeNthModelEps "False"
     .DispersiveFittingSchemeMu "Nth Order"
     .MaximalOrderNthModelFitMu "10"
     .ErrorLimitNthModelFitMu "0.1"
     .UseOnlyDataInSimFreqRangeNthModelMu "False"
     .UseGeneralDispersionEps "False"
     .UseGeneralDispersionMu "False"
     .NLAnisotropy "False"
     .NLAStackingFactor "1"
     .NLADirectionX "1"
     .NLADirectionY "0"
     .NLADirectionZ "0"
     .LatticeScattering "Electron", "0.1", "0."
     .LatticeScattering "Hole", "0.1", "0."
     .EffectiveMassForConductivity "Electron", "0.25"
     .EffectiveMassForConductivity "Hole", "0.35"
     .Colour "0", "0.501961", "0.501961" 
     .Wireframe "False" 
     .Reflection "True" 
     .Allowoutline "True" 
     .Transparentoutline "False" 
     .Transparency "0" 
     .Create
End With

'@ define material: Phone/Coax

'[VERSION]2022.0|31.0.1|20210726[/VERSION]
With Material 
     .Reset 
     .Name "Coax"
     .Folder "Phone"
     .Rho "0.0"
     .ThermalType "Normal"
     .ThermalConductivity "0"
     .SpecificHeat "0", "J/K/kg"
     .DynamicViscosity "0"
     .Emissivity "0"
     .MetabolicRate "0.0"
     .VoxelConvection "0.0"
     .BloodFlow "0"
     .MechanicsType "Unused"
     .IntrinsicCarrierDensity "0"
     .FrqType "all"
     .Type "Normal"
     .MaterialUnit "Frequency", "GHz"
     .MaterialUnit "Geometry", "mm"
     .MaterialUnit "Time", "ns"
     .MaterialUnit "Temperature", "Kelvin"
     .Epsilon "2"
     .Mu "1"
     .Sigma "0"
     .TanD "0.0"
     .TanDFreq "0.0"
     .TanDGiven "False"
     .TanDModel "ConstTanD"
     .SetConstTanDStrategyEps "AutomaticOrder"
     .ConstTanDModelOrderEps "3"
     .DjordjevicSarkarUpperFreqEps "0"
     .SetElParametricConductivity "False"
     .ReferenceCoordSystem "Global"
     .CoordSystemType "Cartesian"
     .SigmaM "0"
     .TanDM "0.0"
     .TanDMFreq "0.0"
     .TanDMGiven "False"
     .TanDMModel "ConstTanD"
     .SetConstTanDStrategyMu "AutomaticOrder"
     .ConstTanDModelOrderMu "3"
     .DjordjevicSarkarUpperFreqMu "0"
     .SetMagParametricConductivity "False"
     .DispModelEps  "None"
     .DispModelMu "None"
     .DispersiveFittingSchemeEps "Nth Order"
     .MaximalOrderNthModelFitEps "10"
     .ErrorLimitNthModelFitEps "0.1"
     .UseOnlyDataInSimFreqRangeNthModelEps "False"
     .DispersiveFittingSchemeMu "Nth Order"
     .MaximalOrderNthModelFitMu "10"
     .ErrorLimitNthModelFitMu "0.1"
     .UseOnlyDataInSimFreqRangeNthModelMu "False"
     .UseGeneralDispersionEps "False"
     .UseGeneralDispersionMu "False"
     .NLAnisotropy "False"
     .NLAStackingFactor "1"
     .NLADirectionX "1"
     .NLADirectionY "0"
     .NLADirectionZ "0"
     .LatticeScattering "Electron", "0.1", "0."
     .LatticeScattering "Hole", "0.1", "0."
     .EffectiveMassForConductivity "Electron", "0.25"
     .EffectiveMassForConductivity "Hole", "0.35"
     .Colour "0.501961", "1", "0.501961" 
     .Wireframe "False" 
     .Reflection "False" 
     .Allowoutline "True" 
     .Transparentoutline "False" 
     .Transparency "0" 
     .Create
End With

'@ define material: Phone/Vacuum

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
With Material 
     .Reset 
     .Name "Vacuum"
     .Folder "Phone"
     .Rho "0.0"
     .ThermalType "Normal"
     .ThermalConductivity "0"
     .SpecificHeat "0", "J/K/kg"
     .DynamicViscosity "0"
     .Emissivity "0"
     .MetabolicRate "0.0"
     .VoxelConvection "0.0"
     .BloodFlow "0"
     .MechanicsType "Unused"
     .IntrinsicCarrierDensity "0"
     .FrqType "all"
     .Type "Normal"
     .MaterialUnit "Frequency", "GHz"
     .MaterialUnit "Geometry", "mm"
     .MaterialUnit "Time", "s"
     .Epsilon "1"
     .Mu "1"
     .Sigma "0"
     .TanD "0.0"
     .TanDFreq "0.0"
     .TanDGiven "False"
     .TanDModel "ConstSigma"
     .SetConstTanDStrategyEps "AutomaticOrder"
     .ConstTanDModelOrderEps "3"
     .DjordjevicSarkarUpperFreqEps "0"
     .SetElParametricConductivity "False"
     .ReferenceCoordSystem "Global"
     .CoordSystemType "Cartesian"
     .SigmaM "0"
     .TanDM "0.0"
     .TanDMFreq "0.0"
     .TanDMGiven "False"
     .TanDMModel "ConstSigma"
     .SetConstTanDStrategyMu "AutomaticOrder"
     .ConstTanDModelOrderMu "3"
     .DjordjevicSarkarUpperFreqMu "0"
     .SetMagParametricConductivity "False"
     .DispModelEps  "None"
     .DispModelMu "None"
     .DispersiveFittingSchemeEps "Nth Order"
     .MaximalOrderNthModelFitEps "10"
     .ErrorLimitNthModelFitEps "0.1"
     .UseOnlyDataInSimFreqRangeNthModelEps "False"
     .DispersiveFittingSchemeMu "Nth Order"
     .MaximalOrderNthModelFitMu "10"
     .ErrorLimitNthModelFitMu "0.1"
     .UseOnlyDataInSimFreqRangeNthModelMu "False"
     .UseGeneralDispersionEps "False"
     .UseGeneralDispersionMu "False"
     .NLAnisotropy "False"
     .NLAStackingFactor "1"
     .NLADirectionX "1"
     .NLADirectionY "0"
     .NLADirectionZ "0"
     .LatticeScattering "Electron", "0.1", "0."
     .LatticeScattering "Hole", "0.1", "0."
     .EffectiveMassForConductivity "Electron", "0.25"
     .EffectiveMassForConductivity "Hole", "0.35"
     .Colour "0.5", "0.8", "1" 
     .Wireframe "False" 
     .Reflection "False" 
     .Allowoutline "True" 
     .Transparentoutline "False" 
     .Transparency "30" 
     .Create
End With

'@ execute macro: SetCoaxFilling

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
'## Merged Block - change material: Phone/Antennas/5G Antenna Array1 1x4:CoaxFill to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array1 1x4:CoaxFill", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array1 1x4:CoaxFill_1 to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array1 1x4:CoaxFill_1", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array1 1x4:CoaxFill_2 to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array1 1x4:CoaxFill_2", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array1 1x4:CoaxFill_3 to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array1 1x4:CoaxFill_3", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array1 1x4:FeedFill to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array1 1x4:FeedFill", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array2 1x4:CoaxFill to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array2 1x4:CoaxFill", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array2 1x4:CoaxFill_1 to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array2 1x4:CoaxFill_1", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array2 1x4:CoaxFill_2 to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array2 1x4:CoaxFill_2", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array2 1x4:CoaxFill_3 to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array2 1x4:CoaxFill_3", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array2 1x4:FeedFill to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array2 1x4:FeedFill", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array3 2x2:FeedFill to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array3 2x2:FeedFill", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array3 2x2:Outer1H to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array3 2x2:Outer1H", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array3 2x2:Outer1V to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array3 2x2:Outer1V", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array3 2x2:Outer2H to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array3 2x2:Outer2H", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array3 2x2:Outer2V to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array3 2x2:Outer2V", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array3 2x2:Outer3H to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array3 2x2:Outer3H", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array3 2x2:Outer3V to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array3 2x2:Outer3V", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array3 2x2:Outer4H to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array3 2x2:Outer4H", "Phone/Coax"

'## Merged Block - change material: Phone/Antennas/5G Antenna Array3 2x2:Outer4V to: Phone/Coax
StartVersionStringOverrideMode "2022.0|31.0.1|20210726" 
Solid.ChangeMaterial "Phone/Antennas/5G Antenna Array3 2x2:Outer4V", "Phone/Coax"
StopVersionStringOverrideMode

'@ pick edge

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickEdgeFromId "Phone/Antennas/5G Antenna Array1 1x4:Pin_3", "3", "3"

'@ pick edge

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickEdgeFromId "Phone/Antennas/5G Antenna Array1 1x4:CoaxFill_3", "9", "9"

'@ define discrete face port: 1

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With DiscreteFacePort 
     .Reset 
     .PortNumber "1" 
     .Type "SParameter"
     .Label "Array1"
     .Folder ""
     .Impedance "50.0"
     .VoltagePortImpedance "0.0"
     .VoltageAmplitude "1.0"
     .CurrentAmplitude "1.0"
     .Monitor "False"
     .CenterEdge "True"
     .SetP1 "True", "92.625281", "-32.24", "-4.3"
     .SetP2 "True", "92.850481", "-32.24", "-4.3"
     .LocalCoordinates "False"
     .InvertDirection "False"
     .UseProjection "False"
     .ReverseProjection "False"
     .FaceType "Linear"
     .Create 
End With

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickExtraCirclepointFromId "Phone/Antennas/5G Antenna Array1 1x4:CoaxFill_3", "9", "13", "1"

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickExtraCirclepointFromId "Phone/Antennas/5G Antenna Array1 1x4:CoaxFill_2", "11", "16", "1"

'@ transform port: translate port1 (Array1)

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With Transform 
     .Reset 
     .Name "port1 (Array1)" 
     .Vector "-5.42", "0", "0" 
     .UsePickedPoints "True" 
     .InvertPickedPoints "False" 
     .MultipleObjects "True" 
     .GroupObjects "False" 
     .Repetitions "3" 
     .MultipleSelection "False" 
     .Transform "Port", "Translate" 
End With

'@ pick edge

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickEdgeFromId "Phone/Antennas/5G Antenna Array2 1x4:Pin_1", "5", "5"

'@ pick edge

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickEdgeFromId "Phone/Antennas/5G Antenna Array2 1x4:CoaxFill_1", "15", "15"

'@ define discrete face port: 5

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With DiscreteFacePort 
     .Reset 
     .PortNumber "5" 
     .Type "SParameter"
     .Label "Array2"
     .Folder ""
     .Impedance "50.0"
     .VoltagePortImpedance "0.0"
     .VoltageAmplitude "1.0"
     .CurrentAmplitude "1.0"
     .Monitor "False"
     .CenterEdge "True"
     .SetP1 "True", "72.405281", "32.24", "-4.2999999999999"
     .SetP2 "True", "72.180081", "32.24", "-4.2999999999999"
     .LocalCoordinates "False"
     .InvertDirection "False"
     .UseProjection "False"
     .ReverseProjection "False"
     .FaceType "Linear"
     .Create 
End With

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickEndpointFromId "Phone/Antennas/5G Antenna Array2 1x4:CoaxFill_1", "15"

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickEndpointFromId "Phone/Antennas/5G Antenna Array2 1x4:CoaxFill", "13"

'@ transform port: translate port5 (Array2)

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With Transform 
     .Reset 
     .Name "port5 (Array2)" 
     .Vector "-5.42", "0", "0" 
     .UsePickedPoints "True" 
     .InvertPickedPoints "False" 
     .MultipleObjects "True" 
     .GroupObjects "False" 
     .Repetitions "3" 
     .MultipleSelection "False" 
     .Transform "Port", "Translate" 
End With

'@ pick edge

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickEdgeFromId "Phone/Antennas/5G Antenna Array3 2x2:Pin1H", "1", "1"

'@ pick edge

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickEdgeFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer1H", "1", "1"

'@ define discrete face port: 9

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With DiscreteFacePort 
     .Reset 
     .PortNumber "9" 
     .Type "SParameter"
     .Label "Array3-H"
     .Folder ""
     .Impedance "50.0"
     .VoltagePortImpedance "0.0"
     .VoltageAmplitude "1.0"
     .CurrentAmplitude "1.0"
     .Monitor "False"
     .CenterEdge "True"
     .SetP1 "True", "8.24016135457", "21.771759585343", "-3.5499116011277"
     .SetP2 "True", "8.24016135457", "21.976759585343", "-3.5499116011277"
     .LocalCoordinates "False"
     .InvertDirection "False"
     .UseProjection "False"
     .ReverseProjection "False"
     .FaceType "Linear"
     .Create 
End With

'@ pick edge

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickEdgeFromId "Phone/Antennas/5G Antenna Array3 2x2:Pin1V", "1", "1"

'@ pick edge

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickEdgeFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer1V", "1", "1"

'@ define discrete face port: 10

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With DiscreteFacePort 
     .Reset 
     .PortNumber "10" 
     .Type "SParameter"
     .Label "Array3-V"
     .Folder ""
     .Impedance "50.0"
     .VoltagePortImpedance "0.0"
     .VoltageAmplitude "1.0"
     .CurrentAmplitude "1.0"
     .Monitor "False"
     .CenterEdge "True"
     .SetP1 "True", "9.25016135457", "22.681759585343", "-3.5499116011277"
     .SetP2 "True", "9.25016135457", "22.476759585343", "-3.5499116011277"
     .LocalCoordinates "False"
     .InvertDirection "False"
     .UseProjection "False"
     .ReverseProjection "False"
     .FaceType "Linear"
     .Create 
End With

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickExtraCirclepointFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer1H", "1", "6", "0"

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickExtraCirclepointFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer2H", "1", "6", "0"

'@ transform port: translate port9 (Array3-H)

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With Transform 
     .Reset 
     .Name "port9 (Array3-H)" 
     .Vector "0", "-5.3571428571429", "0" 
     .UsePickedPoints "True" 
     .InvertPickedPoints "False" 
     .MultipleObjects "True" 
     .GroupObjects "False" 
     .Repetitions "1" 
     .MultipleSelection "False" 
     .Transform "Port", "Translate" 
End With

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickEndpointFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer1V", "1"

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickEndpointFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer2V", "1"

'@ transform port: translate port10 (Array3-V)

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With Transform 
     .Reset 
     .Name "port10 (Array3-V)" 
     .Vector "0", "-5.3571428571428", "0" 
     .UsePickedPoints "True" 
     .InvertPickedPoints "False" 
     .MultipleObjects "True" 
     .GroupObjects "False" 
     .Repetitions "1" 
     .MultipleSelection "False" 
     .Transform "Port", "Translate" 
End With

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickExtraCirclepointFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer1H", "1", "6", "0"

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickExtraCirclepointFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer4H", "1", "6", "0"

'@ transform port: translate port9 (Array3-H)

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With Transform 
     .Reset 
     .Name "port9 (Array3-H)" 
     .Vector "-5.3571428571428", "0", "0" 
     .UsePickedPoints "True" 
     .InvertPickedPoints "False" 
     .MultipleObjects "True" 
     .GroupObjects "False" 
     .Repetitions "1" 
     .MultipleSelection "False" 
     .Transform "Port", "Translate" 
End With

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickExtraCirclepointFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer1V", "1", "6", "1"

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickExtraCirclepointFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer4V", "1", "6", "1"

'@ transform port: translate port10 (Array3-V)

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With Transform 
     .Reset 
     .Name "port10 (Array3-V)" 
     .Vector "-5.3571428571428", "0", "0" 
     .UsePickedPoints "True" 
     .InvertPickedPoints "False" 
     .MultipleObjects "True" 
     .GroupObjects "False" 
     .Repetitions "1" 
     .MultipleSelection "False" 
     .Transform "Port", "Translate" 
End With

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickExtraCirclepointFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer2H", "1", "6", "0"

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickExtraCirclepointFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer3H", "1", "6", "0"

'@ transform port: translate port11 (Array3-H)

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With Transform 
     .Reset 
     .Name "port11 (Array3-H)" 
     .Vector "-5.3571428571428", "0", "0" 
     .UsePickedPoints "True" 
     .InvertPickedPoints "False" 
     .MultipleObjects "True" 
     .GroupObjects "False" 
     .Repetitions "1" 
     .MultipleSelection "False" 
     .Transform "Port", "Translate" 
End With

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickExtraCirclepointFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer2V", "1", "6", "1"

'@ pick end point

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Pick.PickExtraCirclepointFromId "Phone/Antennas/5G Antenna Array3 2x2:Outer3V", "1", "6", "1"

'@ transform port: translate port12 (Array3-V)

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
With Transform 
     .Reset 
     .Name "port12 (Array3-V)" 
     .Vector "-5.3571428571428", "0", "0" 
     .UsePickedPoints "True" 
     .InvertPickedPoints "False" 
     .MultipleObjects "True" 
     .GroupObjects "False" 
     .Repetitions "1" 
     .MultipleSelection "False" 
     .Transform "Port", "Translate" 
End With

'@ add items to group: "AntennaMetals"

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
Group.AddItem "solid$Phone/Antennas/5G Antenna Array1 1x4:Parasitic", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array1 1x4:Parasitic_1", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array1 1x4:Parasitic_2", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array1 1x4:Parasitic_3", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array1 1x4:Patch", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array1 1x4:Patch_1", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array1 1x4:Patch_2", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array1 1x4:Patch_3", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array2 1x4:Parasitic", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array2 1x4:Parasitic_1", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array2 1x4:Parasitic_2", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array2 1x4:Parasitic_3", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array2 1x4:Patch", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array2 1x4:Patch_1", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array2 1x4:Patch_2", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array2 1x4:Patch_3", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Parasitic1", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Parasitic2", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Parasitic3", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Parasitic4", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Patch1", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Patch2", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Patch3", "AntennaMetals"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Patch4", "AntennaMetals"

'@ add items to group: "AntennaPorts"

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
Group.AddItem "solid$Phone/Antennas/5G Antenna Array1 1x4:CoaxFill", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array1 1x4:CoaxFill_1", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array1 1x4:CoaxFill_2", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array1 1x4:CoaxFill_3", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array2 1x4:CoaxFill", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array2 1x4:CoaxFill_1", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array2 1x4:CoaxFill_2", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array2 1x4:CoaxFill_3", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Outer1H", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Outer1V", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Outer2H", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Outer2V", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Outer3H", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Outer3V", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Outer4H", "AntennaPorts"
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Outer4V", "AntennaPorts"

'@ add items to group: "Excluded from Simulation"

'[VERSION]2022.0|31.0.1|20210725[/VERSION]
Group.AddItem "solid$Phone/Antennas/CMA_antenna:feed_CMA", "Excluded from Simulation"
Group.AddItem "solid$Phone/Antennas/WiFi_1:feed_WiFi1", "Excluded from Simulation"
Group.AddItem "solid$Phone/Antennas/WiFi_2:feed_WiFi2", "Excluded from Simulation"
Group.AddItem "solid$Phone/Fillers and Shields:foam1", "Excluded from Simulation"
Group.AddItem "solid$Phone/Fillers and Shields:foam2", "Excluded from Simulation"
Group.AddItem "solid$Phone/Fillers and Shields:space", "Excluded from Simulation"
Group.AddItem "solid$Phone/Housing:radome", "Excluded from Simulation"
Group.AddItem "solid$Phone/Housing:radome_1", "Excluded from Simulation"

'@ add items to group: "NoRefinement"

'[VERSION]2022.0|31.0.1|20210720[/VERSION]
Group.AddItem "solid$Phone/Antennas/5G Antenna Array3 2x2:Plinth", "NoRefinement"
Group.AddItem "solid$Phone/Antennas/WiFi_1:diel_WiFi1", "NoRefinement"
Group.AddItem "solid$Phone/Antennas/WiFi_2:diel_WiFi2", "NoRefinement"
Group.AddItem "solid$Phone/Battery:Shell", "NoRefinement"
Group.AddItem "solid$Phone/Camera:Lens", "NoRefinement"
Group.AddItem "solid$Phone/Camera:LensCover", "NoRefinement"
Group.AddItem "solid$Phone/Connector:Filler_p1", "NoRefinement"
Group.AddItem "solid$Phone/Connector:Filler_p2", "NoRefinement"
Group.AddItem "solid$Phone/Fillers and Shields:Bottom_filler", "NoRefinement"
Group.AddItem "solid$Phone/Fillers and Shields:Top_filler", "NoRefinement"
Group.AddItem "solid$Phone/Housing:ring", "NoRefinement"
Group.AddItem "solid$Phone/Housing:speaker", "NoRefinement"
Group.AddItem "solid$Phone/Camera:Module", "NoRefinement"
Group.AddItem "solid$Phone/Camera:Shell", "NoRefinement"
Group.AddItem "solid$Phone/Connector:Shield", "NoRefinement"
Group.AddItem "solid$Phone/PCBs/mmbrd_placeholder/sh_cans:bottom", "NoRefinement"
Group.AddItem "solid$Phone/PCBs/mmbrd_placeholder/sh_cans:top", "NoRefinement"

'@ define farfield monitor: farfield (f=27.5)

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
With Monitor 
     .Reset 
     .Name "farfield (f=27.5)" 
     .Domain "Frequency" 
     .FieldType "Farfield" 
     .MonitorValue "27.5" 
     .ExportFarfieldSource "False" 
     .UseSubvolume "True" 
     .Coordinates "Structure" 
     .SetSubvolume "-14.614719000000001", "121.38528099999999", "-35", "35", "-8.6499999999999986", "0.83031827805903724" 
     .SetSubvolumeOffset "0.5", "0.5", "0.5", "0.5", "0.5", "0.5" 
     .SetSubvolumeInflateWithOffset "True" 
     .SetSubvolumeOffsetType "Absolute" 
     .EnableNearfieldCalculation "True" 
     .Create 
End With

'@ define farfield monitor: farfield (f=28.35)

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
With Monitor 
     .Reset 
     .Name "farfield (f=28.35)" 
     .Domain "Frequency" 
     .FieldType "Farfield" 
     .MonitorValue "28.35" 
     .ExportFarfieldSource "False" 
     .UseSubvolume "True" 
     .Coordinates "Structure" 
     .SetSubvolume "-14.614719000000001", "121.38528099999999", "-35", "35", "-8.6499999999999986", "0.83031827805903724" 
     .SetSubvolumeOffset "0.5", "0.5", "0.5", "0.5", "0.5", "0.5" 
     .SetSubvolumeInflateWithOffset "True" 
     .SetSubvolumeOffsetType "Absolute" 
     .EnableNearfieldCalculation "True" 
     .Create 
End With

'@ set shape accuracy

'[VERSION]2022.0|31.0.1|20210625[/VERSION]
Solid.ShapeVisualizationAccuracy2 "76" 
Solid.ShapeVisualizationOffset "0" 
Pick.ClearAllPicks

'@ define special time domain solver parameters

'[VERSION]2022.0|31.0.1|20210720[/VERSION]
'STEADY STATE
With Solver
     .SteadyStateDurationType "Time"
     .NumberOfPulseWidths "20"
     .SteadyStateDurationTime "2"
     .SteadyStateDurationTimeAsDistance "2837.48"
     .StopCriteriaShowExcitation "False"
     .RemoveAllStopCriteria
     .AddStopCriterion "All S-Parameters", "0.004", "1", "False"
     .AddStopCriterion "Transmission S-Parameters", "0.004", "1", "False"
     .AddStopCriterionWithTargetFrequency "Reflection S-Parameters", "0.004", "1", "True", "27.5,28.35"
     .AddStopCriterion "All Probes", "0.004", "1", "False"
     .AddStopCriterionWithTargetFrequency "All Radiated Powers", "0.004", "1", "True", "27.5,28.35"
     .AddStopCriterion "All Voltage-Current Monitors", "0.004", "1", "False"
End With

'GENERAL
With Solver
     .TimeStepStabilityFactor "1.0"
     .RestartAfterInstabilityAbort "True"
     .AutomaticTimeSignalSampling "True"
     .SuppressTimeSignalStorage "False"
     .ConsiderExcitationForFreqSamplingRate "False"
     .UseBroadBandPhaseShift "False"
     .SetBroadBandPhaseShiftLowerBoundFac "0.3"
     .SetPortShieldingType "NONE"
     .FrequencySamples "1001"
     .ConsiderTwoPortReciprocity "True"
     .EnergyBalanceLimit "0.03"
     .TDRComputation "False"
     .TDRShift50Percent "False"
     .AutoDetectIdenticalPorts "False"
End With

'HEXAHEDRAL
With Solver
     .SetPMLType "CONVPML"
     .UseVariablePMLLayerSizeStandard "False"
     .KeepPMLDepthDuringMeshAdaptationWithVariablePMLLayerSize "False"
     .SetSubcycleState "Automatic"
     .NormalizeToReferenceSignal "False"
     .SetEnhancedPMLStabilization "Automatic"
     .SimplifiedPBAMethod "False"
     .SParaAdjustment "True"
     .PrepareFarfields "False"
     .MonitorFarFieldsNearToModel "True"
     .DiscreteItemUpdate "Distributed"
End With

'MATERIAL
With Solver
     .SurfaceImpedanceOrder "10"
     .ActivatePowerLoss1DMonitor "True"
     .PowerLoss1DMonitorPerSolid "False"
     .Use3DFieldMonitorForPowerLoss1DMonitor "True"
     .UseFarFieldMonitorForPowerLoss1DMonitor "False"
     .UseExtraFreqForPowerLoss1DMonitor "False"
     .ResetPowerLoss1DMonitorExtraFreq
     .SetDispNonLinearMaterialMonitor "False"
     .ActivateDispNonLinearMaterialMonitor "0.0",  "0.005",  "0.0",  "False"
     .SetTimePowerLossSIMaterialMonitor "False"
     .ActivateTimePowerLossSIMaterialMonitor "0.0",  "0.005",  "0.0",  "False"
     .SetTimePowerLossSIMaterialMonitorAverage "False"
     .SetTimePowerLossSIMaterialMonitorAverageRepPeriod "0.0"
     .TimePowerLossSIMaterialMonitorPerSolid "False"
     .ActivateSpaceMaterial3DMonitor "False"
     .Use3DFieldMonitorForSpaceMaterial3DMonitor "True"
     .UseExtraFreqForSpaceMaterial3DMonitor "False"
     .ResetSpaceMaterial3DMonitorExtraFreq
     .SetHFTDDispUpdateScheme "Automatic"
End With

'AR-FILTER
With Solver
     .UseArfilter "False"
     .ArMaxEnergyDeviation "0.1"
     .ArPulseSkip "1"
End With

'WAVEGUIDE
With Solver
     .WaveguidePortGeneralized "True"
     .WaveguidePortModeTracking "False"
     .WaveguidePortROM "False"
     .DispEpsFullDeembedding "False"
     .SetSamplesFullDeembedding "20"
     .AbsorbUnconsideredModeFields "Automatic"
     .SetModeFreqFactor "0.5"
     .AdaptivePortMeshing "True"
     .AccuracyAdaptivePortMeshing "1"
     .PassesAdaptivePortMeshing "4"
End With

'HEXAHEDRAL TLM
With Solver
     .AnisotropicSheetSurfaceType "0"
     .MultiStrandedCableRoute "False"
     .UseAbsorbingBoundary "False"
     .UseDoublePrecision "False"
     .AllowMaterialOverlap "True"
     .ExcitePlanewaveNearModel "False"
     .SetGroundPlane "False"
     .GroundPlane "x", "0.0"
     .NumberOfLayers "5"
     .AverageFieldProbe "False"
     .NormalizeToGaussian "True"
     .TimeSignalSamplingFactor "1"
     .SurfaceCurrentOnMesh "False"
End With

'TLM POSTPROCESSING
With Solver
     .ResetSettings
     .CalculateNearFieldOnCylindricalSurfaces "false", "Coarse" 
     .CylinderGridCustomStep "1" 
     .CalculateNearFieldOnCircularCuts "false" 
     .CylinderBaseCenter "0", "0", "0" 
     .CylinderRadius "3" 
     .CylinderHeight "3" 
     .CylinderSpacing "1" 
     .CylinderResolution "2.0" 
     .CylinderAllPolarization "true" 
     .CylinderRadialAngularVerticalComponents "false" 
     .CylinderMagnitudeOfTangentialConponent "false" 
     .CylinderVm "true" 
     .CylinderDBVm "false" 
     .CylinderDBUVm "false" 
     .CylinderAndFrontAxes "+y", "+z" 
     .ApplyLinearPrediction "false" 
     .Windowing "None" 
     .LogScaleFrequency "false" 
     .AutoFreqStep "true", "1"
     .SetExcitationSignal "None" 
     .SaveSettings
End With

'TETRAHEDRAL
With Solver
     With .SolverSettings ("time domain")
          .SetMeshType "Tetrahedral" 
          .Set "Discretization", "Automatic" 
     End With 
End With

'@ set mesh properties (Hexahedral TLM)

'[VERSION]2022.0|31.0.1|20210726[/VERSION]
With Mesh 
     .MeshType "HexahedralTLM" 
     .SetCreator "High Frequency"
End With 
With MeshSettings 
     .SetMeshType "HexTLM" 
     .Set "Version", 1%
     'MAX CELL - WAVELENGTH REFINEMENT 
     .Set "StepsPerWaveNear", "10" 
     .Set "StepsPerWaveFar", "10" 
     .Set "WavelengthRefinementSameAsNear", "1" 
     'MAX CELL - GEOMETRY REFINEMENT 
     .Set "StepsPerBoxNear", "20" 
     .Set "StepsPerBoxFar", "20" 
     .Set "MaxStepNear", "0" 
     .Set "MaxStepFar", "0" 
     .Set "ModelBoxDescrNear", "maxedge" 
     .Set "ModelBoxDescrFar", "maxedge" 
     .Set "UseMaxStepAbsolute", "0" 
     .Set "GeometryRefinementSameAsNear", "1" 
     'MIN CELL 
     .Set "UseRatioLimitGeometry", "1" 
     .Set "RatioLimitGeometry", "20" 
     .Set "MinStepGeometryX", "0" 
     .Set "MinStepGeometryY", "0" 
     .Set "MinStepGeometryZ", "0" 
     .Set "UseSameMinStepGeometryXYZ", "1" 
End With 
With MeshSettings 
     .Set "PlaneMergeVersion", "2" 
End With 
With MeshSettings 
     .SetMeshType "HexTLM" 
     .Set "FaceRefinementOn", "0" 
     .Set "FaceRefinementPolicy", "2" 
     .Set "FaceRefinementRatio", "2" 
     .Set "FaceRefinementStep", "0" 
     .Set "FaceRefinementNSteps", "2" 
     .Set "EllipseRefinementOn", "0" 
     .Set "EllipseRefinementPolicy", "2" 
     .Set "EllipseRefinementRatio", "2" 
     .Set "EllipseRefinementStep", "0" 
     .Set "EllipseRefinementNSteps", "2" 
     .Set "FaceRefinementBufferLines", "3" 
     .Set "EdgeRefinementOn", "1" 
     .Set "EdgeRefinementPolicy", "1" 
     .Set "EdgeRefinementRatio", "2" 
     .Set "EdgeRefinementStep", "0" 
     .Set "EdgeRefinementBufferLines", "2" 
     .Set "RefineEdgeMaterialGlobal", "0" 
     .Set "RefineAxialEdgeGlobal", "0" 
     .Set "BufferLinesNear", "3" 
     .Set "UseDielectrics", "1" 
     .Set "EquilibrateOn", "1" 
     .Set "Equilibrate", "3" 
     .Set "IgnoreThinPanelMaterial", "1" 
End With 
With MeshSettings 
     .SetMeshType "HexTLM" 
     .Set "SnapToAxialEdges", "1"
     .Set "SnapToPlanes", "1"
     .Set "SnapToSpheres", "0"
     .Set "SnapToEllipses", "1"
     .Set "SnapToCylinders", "1"
     .Set "SnapToCylinderCenters", "1"
     .Set "SnapToEllipseCenters", "1"
     .Set "SnapCellCenters", "1"
     .Set "SnapProbeCellCenters", "0"
End With 
With MeshSettings
     .SetMeshType "HexTLM"
     .Set "LimitCellSizeType", "Maxcellsizeneartomodel"
     .Set "LimitCellSizeAbsolute", "0"
     .Set "UseCellSizeSmoothingRatio", "1"
     .Set "CellSizeSmoothingRatio", "4"
     .Set "LimitCellConnects", "1"
     .Set "PBAMetalAndThin", "1"
     .Set "PBADielectrics", "1"
     .Set "PBATimeStepReduction", "2"
     .Set "UnlumpEdges", "1"
End With
With Discretizer
     .PointAccEnhancement "75"
End With

'@ define time domain solver parameters

'[VERSION]2022.0|31.0.1|20210726[/VERSION]
Mesh.SetCreator "High Frequency" 

With Solver 
     .Method "Hexahedral TLM"
     .SteadyStateLimit "-25"
     .StimulationPort "All"
     .StimulationMode "All"
     .AutoNormImpedance "False"
     .NormingImpedance "50"
     .StoreTDResultsInCache  "False"
     .RunDiscretizerOnly "False"
     .SuperimposePLWExcitation "False"
     .SParaSymmetry "False"
End With

'@ pick end point

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
Pick.PickEndpointFromId "Phone/Housing:speaker", "4"

'@ pick end point

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
Pick.PickEndpointFromId "Phone/Housing:speaker", "2"

'@ pick mean point

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
Pick.MeanLastTwoPoints

'@ activate local coordinates

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
WCS.ActivateWCS "local"

'@ align wcs with point

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
WCS.AlignWCSWithSelected "Point"

'@ rotate wcs

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
WCS.RotateWCS "w", "270.00"

'@ rotate wcs

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
WCS.RotateWCS "u", "180.00"

'@ store wcs: Speaker Point

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
WCS.Store "Speaker Point"

'@ pick end point

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
Pick.PickEndpointFromId "Phone/Housing:ring", "228"

'@ align wcs with point

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
WCS.AlignWCSWithSelected "Point"

'@ set wcs properties

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
With WCS
     .SetNormal "0", "0", "-1"
     .SetOrigin "121.385281", "35", "0"
     .SetUVector "0", "-1", "0"
End With

'@ store wcs: Auto Grip Left

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
WCS.Store "Auto Grip Left"

'@ set wcs properties

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
With WCS
     .SetNormal "0", "0", "-1"
     .SetOrigin "121.385281", "-35", "0"
     .SetUVector "0", "-1", "0"
End With

'@ store wcs: Auto Grip Right

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
WCS.Store "Auto Grip Right"

'@ activate global coordinates

'[VERSION]2022.0|31.0.1|20210730[/VERSION]
WCS.ActivateWCS "global"

'@ farfield plot options

'[VERSION]2022.0|31.0.1|20210921[/VERSION]
With FarfieldPlot 
     .Plottype "3D" 
     .Vary "angle1" 
     .Theta "90" 
     .Phi "90" 
     .Step "1" 
     .Step2 "1" 
     .SetLockSteps "True" 
     .SetPlotRangeOnly "False" 
     .SetThetaStart "0" 
     .SetThetaEnd "180" 
     .SetPhiStart "0" 
     .SetPhiEnd "360" 
     .SetTheta360 "False" 
     .SymmetricRange "False" 
     .SetTimeDomainFF "False" 
     .SetFrequency "-1" 
     .SetTime "0" 
     .SetColorByValue "True" 
     .DrawStepLines "False" 
     .DrawIsoLongitudeLatitudeLines "False" 
     .ShowStructure "True" 
     .ShowStructureProfile "True" 
     .SetStructureTransparent "False" 
     .SetFarfieldTransparent "False" 
     .AspectRatio "Free" 
     .ShowGridlines "True" 
     .InvertAxes "False", "False" 
     .SetSpecials "enablepolarextralines" 
     .SetPlotMode "Pfield" 
     .Distance "1" 
     .UseFarfieldApproximation "True" 
     .IncludeUnitCellSidewalls "True" 
     .SetScaleLinear "False" 
     .SetLogRange "40" 
     .SetLogNorm "0" 
     .DBUnit "0" 
     .SetMaxReferenceMode "abs" 
     .EnableFixPlotMaximum "False" 
     .SetFixPlotMaximumValue "1.0" 
     .SetInverseAxialRatio "False" 
     .SetAxesType "user" 
     .SetAntennaType "directional_linear" 
     .Phistart "1.000000e+00", "0.000000e+00", "0.000000e+00" 
     .Thetastart "0.000000e+00", "0.000000e+00", "1.000000e+00" 
     .PolarizationVector "0.000000e+00", "1.000000e+00", "0.000000e+00" 
     .SetCoordinateSystemType "ludwig3" 
     .SetAutomaticCoordinateSystem "True" 
     .SetPolarizationType "Slant" 
     .SlantAngle 0.000000e+00 
     .Origin "bbox" 
     .Userorigin "0.000000e+00", "0.000000e+00", "0.000000e+00" 
     .SetUserDecouplingPlane "False" 
     .UseDecouplingPlane "False" 
     .DecouplingPlaneAxis "X" 
     .DecouplingPlanePosition "0.000000e+00" 
     .LossyGround "False" 
     .GroundEpsilon "1" 
     .GroundKappa "0" 
     .EnablePhaseCenterCalculation "False" 
     .SetPhaseCenterAngularLimit "3.000000e+01" 
     .SetPhaseCenterComponent "boresight" 
     .SetPhaseCenterPlane "both" 
     .ShowPhaseCenter "True" 
     .ClearCuts 

     .StoreSettings
End With

'@ align wcs with face

'[VERSION]2022.0|31.0.1|20210921[/VERSION]
Pick.ForceNextPick 
Pick.PickFaceFromId "Phone/Antennas/5G Antenna Array3 2x2:Layer_3", "23" 
WCS.AlignWCSWithSelected "Face"

'@ store wcs: Array3

'[VERSION]2022.0|31.0.1|20210921[/VERSION]
WCS.Store "Array3"

'@ farfield plot options

'[VERSION]2022.0|31.0.1|20210921[/VERSION]
With FarfieldPlot 
     .Plottype "3D" 
     .Vary "angle1" 
     .Theta "90" 
     .Phi "90" 
     .Step "1" 
     .Step2 "1" 
     .SetLockSteps "True" 
     .SetPlotRangeOnly "False" 
     .SetThetaStart "0" 
     .SetThetaEnd "180" 
     .SetPhiStart "0" 
     .SetPhiEnd "360" 
     .SetTheta360 "False" 
     .SymmetricRange "False" 
     .SetTimeDomainFF "False" 
     .SetFrequency "27.5" 
     .SetTime "0" 
     .SetColorByValue "True" 
     .DrawStepLines "False" 
     .DrawIsoLongitudeLatitudeLines "False" 
     .ShowStructure "True" 
     .ShowStructureProfile "True" 
     .SetStructureTransparent "False" 
     .SetFarfieldTransparent "False" 
     .AspectRatio "Free" 
     .ShowGridlines "True" 
     .InvertAxes "False", "False" 
     .SetSpecials "enablepolarextralines" 
     .SetPlotMode "Pfield" 
     .Distance "1" 
     .UseFarfieldApproximation "True" 
     .IncludeUnitCellSidewalls "True" 
     .SetScaleLinear "False" 
     .SetLogRange "40" 
     .SetLogNorm "0" 
     .DBUnit "0" 
     .SetMaxReferenceMode "abs" 
     .EnableFixPlotMaximum "False" 
     .SetFixPlotMaximumValue "1.0" 
     .SetInverseAxialRatio "False" 
     .SetAxesType "user" 
     .SetAntennaType "directional_linear" 
     .Phistart "1.000000e+00", "0.000000e+00", "0.000000e+00" 
     .Thetastart "0.000000e+00", "0.000000e+00", "1.000000e+00" 
     .PolarizationVector "0.000000e+00", "1.000000e+00", "0.000000e+00" 
     .SetCoordinateSystemType "ludwig3" 
     .SetAutomaticCoordinateSystem "True" 
     .SetPolarizationType "Slant" 
     .SlantAngle 0.000000e+00 
     .Origin "zero" 
     .Userorigin "0.000000e+00", "0.000000e+00", "0.000000e+00" 
     .SetUserDecouplingPlane "False" 
     .UseDecouplingPlane "False" 
     .DecouplingPlaneAxis "X" 
     .DecouplingPlanePosition "0.000000e+00" 
     .LossyGround "False" 
     .GroundEpsilon "1" 
     .GroundKappa "0" 
     .EnablePhaseCenterCalculation "False" 
     .SetPhaseCenterAngularLimit "3.000000e+01" 
     .SetPhaseCenterComponent "boresight" 
     .SetPhaseCenterPlane "both" 
     .ShowPhaseCenter "True" 
     .ClearCuts 

     .StoreSettings
End With

'@ activate global coordinates

'[VERSION]2022.0|31.0.1|20210921[/VERSION]
WCS.ActivateWCS "global"

'@ pick center point

'[VERSION]2022.0|31.0.1|20210921[/VERSION]
Pick.PickCenterpointFromId "Phone/Antennas/5G Antenna Array3 2x2:Layer_3", "23"

'@ farfield plot options

'[VERSION]2022.0|31.0.1|20210921[/VERSION]
With FarfieldPlot 
     .Plottype "3D" 
     .Vary "angle1" 
     .Theta "90" 
     .Phi "90" 
     .Step "5" 
     .Step2 "5" 
     .SetLockSteps "True" 
     .SetPlotRangeOnly "False" 
     .SetThetaStart "0" 
     .SetThetaEnd "180" 
     .SetPhiStart "0" 
     .SetPhiEnd "360" 
     .SetTheta360 "False" 
     .SymmetricRange "False" 
     .SetTimeDomainFF "False" 
     .SetFrequency "27.5" 
     .SetTime "0" 
     .SetColorByValue "True" 
     .DrawStepLines "False" 
     .DrawIsoLongitudeLatitudeLines "False" 
     .ShowStructure "True" 
     .ShowStructureProfile "True" 
     .SetStructureTransparent "False" 
     .SetFarfieldTransparent "False" 
     .AspectRatio "Free" 
     .ShowGridlines "True" 
     .InvertAxes "False", "False" 
     .SetSpecials "enablepolarextralines" 
     .SetPlotMode "Pfield" 
     .Distance "1" 
     .UseFarfieldApproximation "True" 
     .IncludeUnitCellSidewalls "True" 
     .SetScaleLinear "False" 
     .SetLogRange "40" 
     .SetLogNorm "0" 
     .DBUnit "0" 
     .SetMaxReferenceMode "abs" 
     .EnableFixPlotMaximum "False" 
     .SetFixPlotMaximumValue "1.0" 
     .SetInverseAxialRatio "False" 
     .SetAxesType "user" 
     .SetAntennaType "directional_linear" 
     .Phistart "1.000000e+00", "0.000000e+00", "0.000000e+00" 
     .Thetastart "0.000000e+00", "0.000000e+00", "1.000000e+00" 
     .PolarizationVector "0.000000e+00", "1.000000e+00", "0.000000e+00" 
     .SetCoordinateSystemType "ludwig3" 
     .SetAutomaticCoordinateSystem "True" 
     .SetPolarizationType "Slant" 
     .SlantAngle 0.000000e+00 
     .Origin "free" 
     .Userorigin "5.560000e+00", "2.000000e+01", "-2.300000e+00" 
     .SetUserDecouplingPlane "False" 
     .UseDecouplingPlane "False" 
     .DecouplingPlaneAxis "X" 
     .DecouplingPlanePosition "0.000000e+00" 
     .LossyGround "False" 
     .GroundEpsilon "1" 
     .GroundKappa "0" 
     .EnablePhaseCenterCalculation "False" 
     .SetPhaseCenterAngularLimit "3.000000e+01" 
     .SetPhaseCenterComponent "boresight" 
     .SetPhaseCenterPlane "both" 
     .ShowPhaseCenter "True" 
     .ClearCuts 

     .StoreSettings
End With

'@ clear picks

'[VERSION]2022.0|31.0.1|20210921[/VERSION]
Pick.ClearAllPicks

'@ define tlm solver excitation modes

'[VERSION]2024.0|33.0.1|20230801[/VERSION]
With TlmSolver 
     .ResetExcitationModes 
     .SParameterPortExcitation "True" 
     .SimultaneousExcitation "False" 
     .SetSimultaneousExcitAutoLabel "True" 
     .SetSimultaneousExcitationLabel "9[1.0,0.0]+11[1.0,0.0]+13[1.0,0.0]+15[1.0,0.0],[15]" 
     .SetSimultaneousExcitationOffset "Phaseshift" 
     .PhaseRefFrequency "15" 
     .ExcitationSelectionShowAdditionalSettings "False" 
     .ExcitationPortMode "1", "1", "1.0", "0.0", "default", "False" 
     .ExcitationPortMode "2", "1", "1.0", "0.0", "default", "False" 
     .ExcitationPortMode "3", "1", "1.0", "0.0", "default", "False" 
     .ExcitationPortMode "4", "1", "1.0", "0.0", "default", "False" 
     .ExcitationPortMode "5", "1", "1.0", "0.0", "default", "False" 
     .ExcitationPortMode "6", "1", "1.0", "0.0", "default", "False" 
     .ExcitationPortMode "7", "1", "1.0", "0.0", "default", "False" 
     .ExcitationPortMode "8", "1", "1.0", "0.0", "default", "False" 
     .ExcitationPortMode "9", "1", "1.0", "0.0", "default", "True" 
     .ExcitationPortMode "10", "1", "1.0", "0.0", "default", "False" 
     .ExcitationPortMode "11", "1", "1.0", "0.0", "default", "True" 
     .ExcitationPortMode "12", "1", "1.0", "0.0", "default", "False" 
     .ExcitationPortMode "13", "1", "1.0", "0.0", "default", "True" 
     .ExcitationPortMode "14", "1", "1.0", "0.0", "default", "False" 
     .ExcitationPortMode "15", "1", "1.0", "0.0", "default", "True" 
     .ExcitationPortMode "16", "1", "1.0", "0.0", "default", "False" 
End With

'@ define time domain solver parameters

'[VERSION]2024.0|33.0.1|20230801[/VERSION]
Mesh.SetCreator "High Frequency" 

With Solver 
     .Method "Hexahedral TLM"
     .SteadyStateLimit "-25"
     .StimulationPort "Selected"
     .StimulationMode "All"
     .AutoNormImpedance "False"
     .NormingImpedance "50"
     .StoreTDResultsInCache  "False"
     .RunDiscretizerOnly "False"
     .SuperimposePLWExcitation "False"
     .SParaSymmetry "False"
End With

