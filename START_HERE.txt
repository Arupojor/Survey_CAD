SURVEY CAD v3 - EMBANKMENT AND RIVER / KHAL
Built by Engr. Arup Chakraborty, Executive Engineer, BWDB

START
Extract the ZIP to a folder. Double-click Embankment and Khal CAD v3.exe. Python and Excel are not required to run it. Keep converter_path.txt beside the executable if using the existing local DWG converter; on another computer, select that computer's ODAFileConverter.exe in the app. DXF export needs no converter.

1. Open your Excel workbook or CSV and click Analyze / recalculate.
   The Area and Cross Section worksheets are recognized automatically. Workbook formula values must have been recalculated and saved in Excel.
2. Cross-sections shows Mean RL and coordinate-bounded fill/cut areas side by side. Scroll horizontally if needed.
3. Open Long profile. Select Embankment or River / Khal, then identify the lower-offset side (C/S or R/S, or Left bank or Right bank).
4. Select a chainage and Edit selected offsets. Review the centreline, low-side and high-side toe/bank offsets. You can leave an unavailable offset blank. Mark the reviewed checkbox only after checking the section. For many sections, Save offset mapping, edit the CSV, and Import offset mapping. Zero is a valid offset.
5. Use Design RL / gradient to review or edit the design schedule. Set constant Top RL for embankment, or start RL and rising/falling gradient for khal. The continuous-grade calculator uses chainage in metres. You can also import reach endpoints from Design_grade.csv. Blank or uncovered reaches remain gaps.
6. Export drawings & tables. DXF works directly. DWG additionally uses the local converter and checks a round trip back to DXF.

LONG PROFILE
Seven series: independent design Top RL / khal bed RL, plus pre/post centreline, pre/post low-side feature, pre/post high-side feature. Side labels become C/S and R/S toe or left and right bank after you choose orientation. The same selected offset is used for pre and post RL at each station, to make a like-for-like comparison.

Suggestions are NOT surveyed feature identifications. Embankment suggestions use the midpoint of the unique highest flat post-work crest and adjacent post vertices as candidate toes. Khal suggestions use the midpoint of the unique lowest flat post-work bed and the highest pre-work point on either side as candidate banks. These can pick a distant high point; review them against the section and survey notes. No unique flat crest/bed means the app asks for offsets instead. Side orientation defaults to Unconfirmed. All included example profiles are provisional for this reason.

The GUI and browser previews fit display axes independently. Long_profile.dxf uses 20x vertical exaggeration, clearly labelled, for legibility. Long_profile.csv stores actual chainages and RLs. Missing values are gaps, and there is no extrapolation beyond a section. The long profile contains all imported stations, independent of volume limits/exclusions. Cross-section CAD geometry remains true 1:1 metres on BOTH axes for area checking.

AREA METHODS
Mean RL / trapezoidal strips: sum of strip width times mean pre/post RL difference, splitting at profile crossings and separating fill from cut.
Coordinate-bounded area: form closed polygons between profiles, split at crossings, and apply A = abs(sum(Xi*Yi+1 - Xi+1*Yi))/2 to each polygon. Sum fill and cut separately. Net = fill minus cut.
For the same piecewise-straight profiles these are mathematically equivalent; the app does not manufacture different answers. The calculations are independent and their differences are reported. This does not call the proprietary AutoCAD calculation engine. To check natively, use AREA > Object or Properties on the closed FILL_BOUNDARY and CUT_BOUNDARY polylines. Sum the polygons for the section. Long-profile display geometry is not used for area calculations.
Autodesk AREA documentation: https://help.autodesk.com/cloudhelp/2021/ENU/AutoCAD-Core/files/GUID-0591351F-8750-425C-9F1C-98B1C73D9D55.htm

The existing volume calculation remains the average-end-area method, separately for fill and cut. This is a volume method, distinct from the sectional Mean RL area calculation. Source workbook cached areas are included for comparison, without recalculating or modifying the original workbook. The khal workbook uses excavation-positive quantities; this app's signed net is fill minus cut, so excavation has negative net.

DESIGN LEVELS IN THIS RELEASE
Embankment design Top RL: 6.200 m throughout the imported reach.
Goruluda Khal: continuous design RL = -2.150 + 0.000130 x chainage(m), from Ch 0 to 8000 m. This rises 0.013 m per 100 m (1 in 7692.308) with increasing chainage, reaching RL -1.110 m. It uses the first RL and common slope in Gradation (2), removing intermediate design resets as requested.
The dashed design line is independent of measured pre/post profiles. Editing it does not change measured earthwork quantities. Design_grade.csv and Design_basis.txt document the adopted levels.

FILES EXPORTED
Earthwork_sections_and_quantities.dxf (and .dwg when selected)
Long_profile.dxf (and .dwg when selected)
Long_profile.html - portable printable browser chart and RL table
Long_profile.csv - actual feature levels by chainage
Feature_offsets.csv - editable centre/toe/bank mapping and reviewed flags
Section_areas.csv - independent area calculations and comparison
Bounded_polygon_vertices.csv - numbered closed-boundary vertices and areas
Mean_area_volumes.csv, Source_coordinates.csv, Calculation_details.json

SUPPLIED WORKBOOK FINDINGS
Embankment: 38 sections; full-reach fill 333726.799042 m3, cut 32.405942 m3, net fill 333694.393100 m3.
Goruluda Khal: 46 sections; full-reach cut 153353.025390 m3, fill 114.132953 m3, net excavation 153238.892437 m3.
These are coordinate-derived quantities with no bulking, compaction or settlement allowance.
Khal Ch 2800 m: workbook cached area 23.602000 m2 versus coordinate net excavation 25.436700 m2, a 1.834700 m2 magnitude discrepancy.
Khal Ch 4300 and 4500 m have repeated final offset 24 m. Ch 5000 m has repeated post-work offset 4 m. These are retained as zero-width vertical segments and flagged. At Ch 4500 m the final pre/post RLs differ (1.75 and 2.75); they have not been guessed or corrected. A feature exactly on a vertical jump has ambiguous RL and is left unavailable.

VALIDATION
Tested all four supplied files, crossing profiles, pure cut/fill, negative RLs, repeated vertical offsets, translated coordinates, invalid ordering, mapping round trips and volume clipping/exclusions. DXF closed-polyline areas were independently checked with the CAD library after saving/reopening. Both area methods agree to within 1e-6 m2 (actual maximum about 2.85e-14 m2 for these inputs). GUI widgets and plots passed an automated smoke test. See Validation.json for source warnings and results. AutoCAD itself was not used for testing.

YOUR ORIGINAL FILES
The original E: drive app and workbooks have not been edited. This is a separate updated release. Worked_examples contains generated drawings and tables; Sample_inputs contains unmodified copies of your supplied files.

