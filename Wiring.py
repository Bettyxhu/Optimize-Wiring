#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
READ THE README.TXT
    
@author: Betty Hu (betty.hu@columbia.edu)
"""

from xlrd import open_workbook
import numpy as np
import matplotlib.pyplot as plt
    
def pop_array(row_num, sheet):
    
    dummy = []
    i = 0
    for cell in sheet.row(row_num):
        cell_s = str(cell)
        if i != 0: # Skip first cell (label)
            j = cell_s.index(':')
            dummy.append(float(cell_s[(j + 1) :]))
        i += 1
    return dummy

def cond_curves(file_name):
    
    # file_name will have a / because that's how they are named in the catalog
    # However, the .txt file names have a . instead
    i = file_name.index('/')
    new_file_name = file_name[0 : i] + '.' + file_name[(i + 1) :]
    try: 
        curve = open(new_file_name, 'r')
    # Print statement for if the file we are trying to find does not exist
    except FileNotFoundError:
        print(new_file_name + ' not found')
        return 0
    # Skip the first line--no data here
    curve.readline()
    
    T = []
    cond = []
    last_line_true = 1
    while last_line_true:
        current_line = curve.readline()
        try:
            j = current_line.index(',')
        except ValueError:
            j = -1
        if j == -1:
            break
        T.append(float(current_line[0 : j]))
        cond.append(float(current_line[(j + 2) :]))
        
    # T_cond is a list where the first row is a list of temperature data
    # and the second row is a list of kA/l data
    T_cond = []
    T_cond.append([])
    T_cond.append([])
    T_cond[0] = T
    T_cond[1] = cond
    
    return T_cond

def pick_wires(T1, T2, p, l, x, wires, names, output_file):
    
    ''' Give high temp and low temp (K), thermal loading (W), length of wire (cm), 
    +/- x% for acceptable wire length, wires array, and names array:
        Wires array:
            First row: conductivity curves for each cable
            Second row: attenuation at 300K for each cable
            Third row: attenuation at 4K for each cable 
            Fourth row: whether or not wire is superconducting (1 or 0) ''' 
    
    # Create lists that will eventually hold properties of wires that fit
    # given parameters
    ok_length = []
    ok_power = []
    ok_att = []
    ok_name = []
    
    # Make lists of lengths that we are iterating through
    if x > 0:
        l_range = np.linspace(l - l * (x / 100), l + l * (x / 100), 5)
        l_range = np.ndarray.tolist(l_range)
    else:
        l_range = np.linspace(l, l, 1)
        l_range = np.ndarray.tolist(l_range)

    for length in l_range:
        wire_i = 0
        for current_cond in wires[0]:
            # If no conductivity curve exists, then skip the wire
            if current_cond == 0:
                wire_i += 1
                continue
            # If superconducting, we only want to consider it if T1 <= 5.9 K
            # It wouldn't make sense to consider a superconducting wire otherwise
            if wires[3][wire_i] == 1:
                if T1 > 5.9:
                    wire_i += 1
                    continue
                else: # Complete the curve and continue
                    complete_cond = complete_curve(current_cond, names[wire_i])
            # If not superconducting
            if wires[3][wire_i] == 0:
                complete_cond = complete_curve(current_cond, names[wire_i])
            current_pow = calc_power(complete_cond, T1, T2, length)
            # Check if thermal loading is <= given power threshold
            if names[wire_i] == 'SC-086/50-CN-CN':
                print(names[wire_i])
                print(current_pow)
            if current_pow <= p and current_pow > 0:
                ok_length.append(length)
                ok_power.append(current_pow)
                # Fit line for att/l vs T betw 4 and 300K and use to find att/l for 
                # other T points, but only if other T is between 4 and 300K
                if T1 >= 4: 
                    ok_att.append(total_att(T1, wires[1][wire_i], wires[2][wire_i]) * length / 100)
                # Otherwise just use 4K value to be safe
                else: 
                    ok_att.append(wires[1][wire_i] * length / 100)
                ok_name.append(names[wire_i])
            wire_i += 1
            
    # Now we want to sort our wires from lowest --> highest attenuation
    sort_wires(ok_length, ok_power, ok_att, ok_name, output_file)
    
def calc_power(cond_curve, T1, T2, length):
    
    ''' This function calculates the thermal loading for a given wire,
    given the temperature range and its conductivity curve and length '''
    
    i = 0
    power = 0
    
    # P = cond * dTemp / l
    # "Integral" with ~ 0.2K spacing
    for temp in cond_curve[0]:
        # Check that current temperature is within the range we are interested in
        if temp >= T2 and temp <= T1:
            if i == 0:
                power += cond_curve[1][i] * temp / length
            else:
                power += cond_curve[1][i] * (temp - cond_curve[0][i - 1]) / length
        i += 1
    
    return power

def complete_curve(cond_curve, name):
    
    ''' The purpose of this function is to take the data we have from coax.co,
    which is limited in temperature range, and extend the data from 250 mK
    to 300 K '''
        
    low_temp = cond_curve[0][0]
    high_temp = cond_curve[0][len(cond_curve[0]) - 1]
    low_cond = cond_curve[1][0]
    high_cond = cond_curve[1][len(cond_curve[1]) - 1]
    polynom = 0
    
    # Beryllium copper
    if 'B-B' in name:
        material = 'B'
    # Stainless steel, but note that this will also capture silver-coated stainless steel
    # For now, we are assuming that the two act the same at temperatures > ~6 K
    elif 'SS-SS' in name:
        material = 'SS'
    # Cupronickel, but note that this will also capture silver-coated cupronickel
    # For now, we are assuming that the two act the same at temperatures > ~6 K
    elif 'CN-CN' in name:
        material = 'CN'
    else:
        material = 'polynom'
        poly_coeff = np.polyfit(cond_curve[0], cond_curve[1], 2)
        polynom = np.poly1d(poly_coeff)
     
    # Multiplicative factor between calculated k and k from coax.co graph
    offset = calc_k(high_temp, material) / high_cond
    
    # Complete high end of curve
    while cond_curve[0][len(cond_curve[0]) - 1] < 300.1:
        # Add a temperature point that is 0.02 K higher than the previous highest
        cond_curve[0].append(cond_curve[0][len(cond_curve[0]) - 1] + 0.02)
        # Add a conductivity point
        if polynom:
            cond_curve[1].append(polynom(cond_curve[0][len(cond_curve[0]) - 1]))
        else:
            cond_curve[1].append(calc_k(cond_curve[0][len(cond_curve[0]) - 1], material) / offset)
        
    # Complete low end of curve by just extending lowest cond point to 250 mK
    while cond_curve[0][0] > 0.250:
        cond_curve[0].insert(0, cond_curve[0][0] - 0.02)
        cond_curve[1].insert(0, low_cond)
        
    return cond_curve
    
def total_att(T1, att_300, att_4):
    
    ''' Draw a straight line between attenuation at 300 K and 4 K, then 
    use this line to estimate attenuation at a temperature in between'''
    
    m = (att_300 - att_4) / (300 - 4)
    att_T1 = m * T1 + att_4
    
    return att_T1

def sort_wires(lengths, powers, atts, names, output_file):
    
    ''' Sort given wires by attenuation, low to high '''
    
    sort_lengths = []
    sort_powers = []
    sort_atts = []
    sort_names = []
    
    while len(atts) > 0:
        min_att = min(atts)
        min_att_i = atts.index(min_att)
        sort_lengths.append(lengths[min_att_i])
        sort_powers.append(powers[min_att_i])
        sort_atts.append(atts[min_att_i])
        if names[min_att_i] in sort_names:
            i = 2
            while i <= 5:
                temp_name = names[min_att_i] + ' (' + str(i) + ')'
                if temp_name not in sort_names:
                    sort_names.append(temp_name)
                    break
                else:
                    i += 1
        else:
            sort_names.append(names[min_att_i])
        lengths.pop(min_att_i)
        powers.pop(min_att_i)
        atts.pop(min_att_i)
        names.pop(min_att_i)
    
    write_to_text(sort_lengths, sort_powers, sort_atts, sort_names, output_file)
    
def write_to_text(lengths, powers, atts, names, file_name):
    
    ''' Creates a text file that lists acceptable wires and their properties '''
    
    wires = open(file_name, 'w')
    col_format = '{:<25}' * 4 + '\n' 
    lengths.insert(0, 'Length (cm)')
    powers.insert(0, 'Power (W):')
    atts.insert(0, 'Attenuation (dB):')
    names.insert(0, 'Name:')
    for row in zip(names, atts, powers, lengths):
        wires.write(col_format.format(*row))
        
def choose_freq(att_f1, att_f2, f1, f2, final_f):
    
    ''' f1 should be the higher frequency, and final_f should be between f1 
    and f2. We draw a straight line between the attenuation at the two, then
    use this line to estimate the attenuation at a frequency in between'''
    
    att_new = []
    i = 0
    for att in att_f1:
        m  = (att_f1[i] - att_f2[i]) / (f1 - f2)
        att_new.append(final_f * m + att_f2[i])
        i += 1
    return att_new

def calc_k(T, material):
    
    ''' We calculate k from various sources '''
    
    # For B and SS, we use this paper:
        # http://cryogenics.nist.gov/Papers/Cryo_Materials.pdf
    if material == 'B': # Beryllium copper
        a = -0.50015
        b = 1.93190
        c = -1.69540
        d = 0.71218
        e = 1.27880
        f = -1.61450
        g = 0.68722
        h = -0.10501
        i = 0
    elif material == 'SS': # Stainless steel
        a = -1.4087
        b = 1.3982
        c = 0.2543
        d = -.626
        e = .2334
        f = .4256
        g = -.4658
        h = .1650
        i = -0.0199
    # This is given as a formula at *4K* thus this needs to be improved
    elif material == 'CN':
        return 300e-4*(T**(1.1))
    else:
        a = 0
        b = 0
        c = 0
        d = 0
        e = 0
        f = 0
        g = 0
        h = 0
        i = 0
        
    # Calculation of k for B and SS
    logT = np.log10(T)
    logk = a + b*logT + c*logT**2 + d*logT**3 + e*logT**4 + f*logT**5 + g*logT**6 + h*logT**7 + i*logT**8
    k = 10**logk
    
    return k
        
def main(T1, T2, p, l, x, output_file):
    
    book = open_workbook('Parts Data.xlsx')
    sheet = book.sheet_by_index(0)

    # Has to be made separately because of string format
    part_nums = []
    i = 0
    for cell in sheet.row(0):
        cell_s = str(cell)
        if i != 0:
            j = cell_s.index(':')
            part_nums.append(cell_s[(j+2):-1])
        i += 1

    # Fill lists for each row
    cond = pop_array(1, sheet)
    att_300_05 = pop_array(2, sheet)
    att_300_1 = pop_array(3, sheet)
    att_300_5 = pop_array(4, sheet)
    att_300_10 = pop_array(5, sheet)
    att_300_20 = pop_array(6, sheet)
    att_4_05 = pop_array(7, sheet)
    att_4_1 = pop_array(8, sheet)
    att_4_5 = pop_array(9, sheet)
    att_4_10 = pop_array(10, sheet)
    att_4_20 = pop_array(11, sheet)
    sup = pop_array(12, sheet)
    
    # Populate wires array for 5 GHz
    wires = []
    wires.append([])
    wires.append([])
    wires.append([])
    wires.append([])
    
    i = 0
    for name in part_nums:
        wires[0].append(cond_curves(name + '.txt'))
        i += 1
    
    wires[1] = choose_freq(att_300_10, att_300_1, 10, 1, 4)
    wires[2] = choose_freq(att_4_10, att_4_1, 10, 1, 4)
    wires[3] = sup
    
    pick_wires(T1, T2, p, l, x, wires, part_nums, output_file)
    
    # Code for test graphs below
    
    '''
    for name in part_nums:
        if name == 'SC-086/50-BS-BS':
            cond = cond_curves(name + '.txt')
            # plt.plot(0.33**(2), cond[1][0], 'ro')
            cond33 = cond[1][0]
            complete = complete_curve(cond, name)
            plt.semilogy(cond[0], cond[1])
        elif name == 'SC-086/50-CN-CN':
            cond = cond_curves(name + '.txt')
            # plt.plot(0.86**(2), cond[1][0], 'ro')
            cond86 = cond[1][0]
            # complete = complete_curve(cond, name)
            plt.semilogy(cond[0], cond[1])
        elif name == 'SC-119/50-CN-CN':
            cond = cond_curves(name + '.txt')
            # plt.plot(1.19**(2), cond[1][0], 'ro')
            cond119 = cond[1][0]
            # complete = complete_curve(cond, name)
            plt.semilogy(cond[0], cond[1])
        elif name == 'SC-219/50-CN-CN':
            cond = cond_curves(name + '.txt')
            # plt.plot(2.19**(2), cond[1][0], 'ro')
            cond219 = cond[1][0]
            # complete = complete_curve(cond, name)
            plt.semilogy(cond[0], cond[1])
    '''

def generate_data_base():
    
    ''' This is the base code. Because you are always working with different
    codes, you should copy and paste this function into a new function and 
    only change that function. The goal of this function is to use data
    from wires of the same material but with different diameters to estimate
    kA/l values for a wire of the same material with a different diameter'''
    
    book = open_workbook('Parts Data.xlsx')
    sheet = book.sheet_by_index(0)

    # Has to be made separately because of string format
    part_nums = []
    i = 0
    for cell in sheet.row(0):
        cell_s = str(cell)
        if i != 0:
            j = cell_s.index(':')
            part_nums.append(cell_s[(j+2):-1])
        i += 1
    
    # First line
    # Note that all this intro text should be kept to one line so that this
    # text file can be read in the same way as existing text files
    newfile = open('SC-358.50-SS-SS.txt', 'w')
    newfile.write(
            'THIS DATA IS GENERATED FROM THE FOLLOWING CALCULATIONS. We fit ' \
            'a line to kA/l vs d**2 for the following diameters: 0.33, 0.86, ' \
            '1.19, and 2.19 mm for 50-SS-SS wires. For each temperature point ' \
            'in the SC-033.50-SS-SS.txt file, we fit a line and used ' \
            ' y = mx + b to calculate a kA/l value for 3.58 mm. \n')
    
    # Importing existing text files
    for name in part_nums:
        if name == 'SC-033/50-SS-SS':
            Tcond33 = cond_curves(name + '.txt')
            T33 = Tcond33[0]
            C33 = Tcond33[1]
        elif name == 'SC-086/50-SS-SS':
            Tcond86 = cond_curves(name + '.txt')
            T86 = Tcond86[0]
            C86 = Tcond86[1]
        elif name == 'SC-119/50-SS-SS':
            Tcond119 = cond_curves(name + '.txt')
            T119 = Tcond119[0]
            C119 = Tcond119[1]
        elif name == 'SC-219/50-SS-SS':
            Tcond219 = cond_curves(name + '.txt')
            T219  = Tcond219[0]
            C219 = Tcond219[1]
            
    # x values of fit are diameters SQUARED of wires with existing data
    x = np.array([0.33**2, 0.86**2, 1.19**2, 2.19**2])

    # br breaks the code if the temperatures go out of bound
    br = 0
    i33 = 0
    # For a given temperature in the temperature list of the thinnest wire,
    # we find the closest temperature (just higher) from the other wires
    for temp33 in T33:
        cond33 = C33[i33]
        if temp33 < T86[0]:
            continue
        elif temp33 < T119[0]:
            continue
        elif temp33 < T219[0]:
            continue
        temp86, temp119, temp219, i86, i119, i219 = 0, 0, 0, 0, 0, 0
        # We want to know the kA/l value associated with the closest temperature
        while temp86 < temp33:
            temp86 = T86[i86]
            cond86 = C86[i86]
            if i86 < (len(T86) - 1):
                i86 += 1
            else:
                br = 1
                break
        while temp119 < temp33:
            temp119 = T119[i119]
            cond119 = C119[i119]
            if i119 < (len(T119) - 1):
                i119 += 1
            else:
                br = 1
                break
        while temp219 < temp33:
            temp219 = T219[i219]
            cond219 = C219[i219]
            if i219 < (len(T219) - 1):
                i219 += 1
            else:
                br = 1
                break
        i33 += 1
        # Break the loop completely once we're done iterating through the 
        # temperature range of the thinnest wire
        if br:
            break
        else:
            # y values of fit are the corresponding kA/l values
            y = np.array([cond33, cond86, cond119, cond219])
            # Linear fit, y = mx + b
            m, b = np.polyfit(x, y, 1)
            # Write to new file: temperature, kA/l
            newfile.write(str(temp33) + ', ' + str(m * 3.58**2 + b) + '\n')
        
    print('Reached end of test code')
    
    return

main(350e-3, 250e-3, 10, 10.16, 0, 'test.txt')