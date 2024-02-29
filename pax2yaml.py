from pycomm3 import LogixDriver
from sys import argv
import yaml
from tqdm import trange, tqdm
from itertools import product
import argparse
from collections import OrderedDict
import os
from AOI_definitions import AOI_CONFIG

def get_aoi_tag_instances(plc, tag_type):
    """
    function returns list of tag names matching struct type
    """
    #return tag_list

    tag_list = []

    for tag, _def in plc.tags.items():
        if _def['data_type_name'] == tag_type and not(_def['alias']):
            if _def['dim'] > 0:
                tag_list = tag_list + get_dim_list(tag,_def['dimensions'])
            else:
                tag_list.append(tag)

    return tag_list

def get_dim_list(base_tag, dim_list):
    '''
    function takes a list which has the array size and turns it into a list with all iterations
    '''
    # remove 0's
    filtered_list = list(filter(lambda num: num != 0, dim_list))

    temp = []

    for indices in product(*[range(dim) for dim in filtered_list]):
        temp.append(base_tag + ''.join(f'[{i}]' for i in indices))

    return temp

# append elements to instance of tag
def make_tag_list(base_tag,sub_tags):
    '''
    returns the full tag path of a given base tag and sub tags
    '''
    # concatenate base tag
    read_list = [base_tag + '.' + s for s in sub_tags]

    return read_list

def read_from_plc(plc, tag_list):
    '''
    reads data from plc, returns list of tuples (tag_name, tag_value)
    '''

    if len(tag_list) == 1:  # If only one tag is provided
        tag_data = [plc.read(tag_list[0])]  # Wrap the single tag in a list
    else:
        tag_data = plc.read(*tag_list)

    # List comprehension to format tag data
    tag_data_formatted = [{s[0]: int(s[1]) if s[2] == 'BOOL' else
                           float(format(s[1], '.6e')) if s[2] == 'REAL' and 'e' in str(s[1]) else
                           int(s[1]) if s[2] == 'REAL' and s[1].is_integer() else
                           float(format(s[1], '.6f')) if s[2] == 'REAL' else
                           s[1]} for s in tag_data]

    return tag_data_formatted

def combine_and_modify_dicts(list_of_dicts, part_to_remove):
    '''
    Written by the GOAT GPT
    Combines a list of dictionaries and removes a string from the keys
    '''
    combined_dict = {}
    for dictionary in list_of_dicts:
        combined_dict.update(dictionary)
    
    modified_dict = {key.replace(part_to_remove, ''): value for key, value in combined_dict.items()}
    
    return modified_dict

def save_as_yaml(data, folder1, folder2, filename):
    # Create the nested subfolders if they don't exist
    os.makedirs(os.path.join(folder1, folder2), exist_ok=True)  
    filepath = os.path.join(folder1, folder2, filename)
    with open(filepath, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def make_yaml_for_tag(plc,tag_type,base_tag):
    '''
    Make YAML of Tag Data
    '''
    tag_dict = {}

    tag_dict['AOI'] = tag_type

    # loop through each key in structure
    for yaml_key in AOI_CONFIG[tag_type]:

        # tag list to read
        tags_to_read = make_tag_list(base_tag,AOI_CONFIG[tag_type][yaml_key])

        # read tag data from PLC
        tag_data = read_from_plc(plc,tags_to_read)

        # strip out
        #print(tag_data_formatted)
        tag_data_formatted = combine_and_modify_dicts(tag_data,base_tag + '.')

        tag_dict[yaml_key] = tag_data_formatted

    return tag_dict

def main():
    
    # Parse arguments

    default_directory = ''
   
    parser = argparse.ArgumentParser(
        description='Python-based PlantPAX tag to YAML converter.',
        epilog='This tool works on both Windows and Mac.')
    
    # Add command-line arguments
    parser.add_argument('commpath', help='Path to PLC')
    subparsers = parser.add_subparsers(dest='mode',help='Select read/write mode')

    # parsing read commands, filename is optional and will default to default_yamfile value
    read_parser = subparsers.add_parser('read', help='Read tags from PLC into spreadsheet')
    read_parser.add_argument('directory', nargs='?', default=default_directory,help='Path to excel file')

    # parsing write commands, yamlfile is required
    write_parser = subparsers.add_parser('write', help='Write data from yaml into PLC tags')
    write_parser.add_argument('directory',help='Path to yaml file')
                                       
    args = parser.parse_args()

    # Access the parsed arguments
    commpath = args.commpath
    yamldirectory = args.directory
    mode = args.mode

    # open connection to PLC

    # use yaml template to format which tags to read

    # read tags

    # save yaml file with tagname.yml

    plc = LogixDriver(commpath, init_tags=True,init_program_tags=True)

    print('Connecting to PLC.')
    try:
        plc.open()
        plc_name = plc.get_plc_name()

        default_yamlfile    = plc_name + '_TagValues.yaml'
        print('Connected to ' + plc_name + ' PLC at ' + commpath)
    except:
        print('Unable to connect to PLC at ' + commpath)
        exit()

    # pull data from terrible database
    aoi_list = AOI_CONFIG.keys()

    # read from PLC
    if mode == 'read':
        print('Reading tags from ' + plc_name + ' PLC.')

        for aoi in aoi_list:
            # get setup info from PLC tags, write to spreadsheet
            base_tags = get_aoi_tag_instances(plc,aoi)
            num_instances = len(base_tags)

            if num_instances > 0:

                # get subtag list for given AOI
                #sub_tags = get_subtag_list(book[aoi])

                failed_read_tags = []

                # read rows, write to spreadsheet
                for i in tqdm(range(num_instances),"Reading instances of " + aoi):
                    # make yaml file
                    tag_data_yaml = make_yaml_for_tag(plc,aoi,base_tags[i])

                    # save to file
                    save_as_yaml(tag_data_yaml,yamldirectory,"TagData_" + plc_name,base_tags[i] + '.yml')

                    # add to failed tags list if we can't find the tag
                    #if not all(read_result):
                    #    failed_read_tags = failed_read_tags + get_failed_tags(tag_list,read_result)

                # print to command line if we couldn't read any tags
                if failed_read_tags:
                    print(failed_tag_formatter(failed_read_tags,False))
            else:
                print("No instances of " + aoi + " found in " + plc_name + " PLC.")

if __name__ == "__main__":
    main()