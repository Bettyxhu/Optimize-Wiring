Written by Betty Hu (betty.hu@columbia.edu)
July 17, 2017

The purpose of this script is to take a set of restrictions on the wiring and return a list of wires from coax.co (http://www.coax.co.jp/en/wcaxp/wp-content/themes/coax/pdf/cryogenic_cable_catalogue.pdf) which meet these restrictions, ordered from lowest to highest attenuation. Run this script by calling main(T1, T2, p, l, x, output_file) at the bottom of the script. 

Notes on input:
- T1 and T2 are the high and low temperatures of the temperature stage, respectively, in units of K
- T1 must be higher than T2 (I’m actually not sure what would happen if it isn’t but everything is written with this assumption)
- p is the allowed thermal loading in units of W
- l is the length of the wire in the given temperature stage, in units of cm (!!!)
- x is the allowed % deviation in l. For example, if l = 5 and x = 10, the script will consider wires from lengths 4.5 to 5.5 cm. x can be 0.
- output_file is the name of the text file that will be outputted (currently ‘test.txt’) with the names, attenuation, thermal loading/power, and length of each wire which meets the restrictions

Notes on cables:
- Cables considered come from http://www.coax.co.jp/en/wcaxp/wp-content/themes/coax/pdf/cryogenic_cable_catalogue.pdf
- For each cable, I recorded its part number (ex. SC-033/50-SS-SS), thermal conductivity @4 K (W*cm/K), attenuation @300 K and @4 K for 0.5, 1, 5, 10, and 20 GHz each (dB/m)
- All these variables are recorded in ‘Parts Data.xlsx’ which must be kept in the same folder as the script!
- In addition, I added another variable ‘Superconducting’ which is either 0 (not superconducting) or 1 (superconducting) for each wire, which is used in the code when considering cables (if T1 > 5.9 K, no superconducting wires are considered)

Notes on thermal conductivity:
- Starting on page 9 of the coax.co catalog, there are some thermal conductivity vs temperature curves which I datathiefed and are now included as .txt files in the same folder as the script
- There are two problems with these curves: 1) they provide data no higher than 10 K, and 2) many wires in the catalog don’t have curves ie I have no thermal conductivity data on them at all
- This problem is partially addressed in the code

Notes on code structure:
- main(T1, T2, p, l, x, output_file) takes the aforementioned inputs and opens the Excel spreadsheet
- It actually reads the attenuation data at all frequencies which coax.co provides data for, but internally calls another function choose_freq(att_f1, att_f2, f1, f2, final_f) which takes the 10 GHz and 1 GHz attenuation data and comes up with some 4 GHz data by taking a linear fit between the two
- For each wire, it also looks for a .txt file with *almost* the same name as the wire but with ‘/‘ replaced with ‘.’ (ex. for ’SC-033/50-SS-SS’ it looks for ’SC-033.50-SS-SS.txt’) which holds the aforementioned datathiefed thermal conductivity vs temperature data
- It then calls pick_wires(T1, T2, p, l, x, wires, names, output_file) which is the function which figures out which wires meet the given restrictions
- For now, as it is iterating through the wires, if it comes across a wire without a thermal conductivity curve it just skips the wire and outputs a message that the .txt file was not found
- As it iterates through the wires, superconducting wires are only considered if T1 <= 5.9 K
- It then calls a function complete_curve(cond_curve, name) which attempts to address the problem of the given thermal conductivity curves only extending to 10 K or less
- complete_curve(cond_curve, name) takes a given thermal conductivity curve and the wire’s name and attempts to extend the curve from 250 mK to 300 K:
	- If the wire uses any sort of stainless steel (the name will have ‘SS-SS’), it calculates temperature-dependent k (using http://cryogenics.nist.gov/Papers/Cryo_Materials.pdf), finds some multiplicative offset, and uses that formula to complete the curve up to 300 K
	- Same for if the wire uses beryllium copper (name will have ‘B-B’)
	- Note that right now silver-coated stainless steel (‘SSS-SS’) is treated the same as normal stainless steel (ie assumed same behavior for temperatures > 10 K), this should probably be fixed eventually
	- For extending the conductivity curve down to 250 mK, we just assume whatever the lowest known thermal conductivity is holds down to 250 mK so that we are not trying to calculate a lower-than-possible thermal conductivity
	- For cupronickel (CN-CN), we are calculating k from this paper (http://www.sciencedirect.com/science/article/pii/001122759390027L), which is actually only expected to hold up to 4 K. This should fixed probably.
		- Easiest fix would be deleting lines 177-178 (elif…material = ‘CN’) and just doing a 2nd degree poly fit
	- For all other materials, a 2nd degree polynomial fit is used to calculate thermal conductivity for higher temperatures
		- I’ve tested 3rd degree and higher and they seem to give weird predictions for higher temperature
- Now the conductivity curve is “complete” from 250 mK - 300 K. We use it to calculate the thermal loading in the given temperature stage. If this value is lower than <= p, then we record the current wire’s length, expected thermal loading, and attenuation
	- Because we only have attenuation for 300 K and 4 K, the function total_att(T1, att_300, att_4) takes these two values as well as the highest temperature in the temperature stage and assumes a linear fit between 4 K and 300 K, then returns some in-between value which is assumed to be constant down the wire
	- If the temperature stage is entirely below 4 K, then the 4 K attenuation value is used
- This list of wires and their lengths, expected thermal loading, and attenuation is then written to the output_file in order of lowest to highest attenuation
	- If x != 0, then it is possible for one wire to be listed up to 5 times, ie at every tested length the wire met the thermal loading threshold. Then it is listed multiple times in output_file but with a number next to it indicating the number of times it has been listed.

Notes on adding new wires and generating .txt files:
- If you want to add a new wire, you have to add a new column in ‘Parts Data.xlsx’ and also add a .txt file formatted as follows:
	- The name of the .txt file must be the name of the wire, but with ‘/‘ replaced with ‘.’ (ex. SC-033/50-SS-SS —> SC-033.50-SS-SS.txt)
	- The first line and *only* the first line should contain miscellaneous info. The script that reads .txt files skips *only* the first line when looking for numbers
	- After that, each row should be formatted as: temperature, conductivity in the units K, W*cm/K
- After datathiefing, I ended up missing thermal conductivity curves for some wires but found thad I had curves for the same material wires but with different diameters. So there is a function generate_data_base() which looks at existing thermal conductivity tables and for each temperature point, plots conductivity vs d^2 and uses this to estimate thermal conductivity at that temperature point for the wire with known diameter but unknown thermal conductivity
	- Everything is hard-coded in so if you want to use it you will have to go in and change everything on your own :( 
	- You can figure out which .txt files are “fake” ie generated using this code because I will have written something indicating so in the first line of the .txt file