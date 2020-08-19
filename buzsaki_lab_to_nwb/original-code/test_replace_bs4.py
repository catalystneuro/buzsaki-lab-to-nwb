
from lxml import etree as et

xml_filepath = 'D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903/YutaMouse41-150903.xml'

tree = et.parse(xml_filepath)
root = tree.getroot()


from bs4 import BeautifulSoup

with open(xml_filepath, 'r') as xml_file:
    contents = xml_file.read()
    soup = BeautifulSoup(contents, 'xml')
    
shank_channels_from_soup = [[int(channel.string)
                               for channel in group.find_all('channel')]
                               for group in soup.spikeDetection.channelGroups.find_all('group')]


soup_groups = soup.spikeDetection.channelGroups.find_all('group')

lxml_groups = [et.tostring(x) for x in root.find('spikeDetection').find('channelGroups').findall('group')]

shank_channels_from_lxml = [[int(channel.text)
                                for channel in group.find('channels')]
                                for group in root.find('spikeDetection').find('channelGroups').findall('group')]