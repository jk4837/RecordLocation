import sublime, sublime_plugin
import datetime
import shutil
import os.path
import json
import re
import time

COMPARE_LEN = 40

# >>> sublime.installed_packages_path()
# C:\Users\ChihWan\AppData\Roaming\Sublime Text 3\Installed Packages
# >>> sublime.packages_path()
# C:\Users\ChihWan\AppData\Roaming\Sublime Text 3\Packages
# >>> sublime.cache_path()
# C:\Users\ChihWan\AppData\Local\Sublime Text 3\Cache

class Location(object):
	def __init__(self, file, rowStart, colStart, rowEnd, colEnd, rowViewOffset, colViewOffset, context = '', desc = ''):
		self.file = file
		self.rowStart = rowStart
		self.colStart = colStart
		self.rowEnd = rowEnd
		self.colEnd = colEnd
		self.rowViewOffset = rowViewOffset
		self.colViewOffset = colViewOffset
		self.context = context
		self.desc = desc

def plugin_loaded():
	global data,recFile, reading_list, reading_list_idx
	recFile = os.path.join(sublime.packages_path(), 'User', 'record_location.json')
	reading_list = None;
	reading_list_idx = 0;
	# print('The data is store to \'', recFile, '\'')
	openFile()

def plugin_unloaded():
	saveFile()
	pass

def initData():
	global data
	print('Init data')
	data = {}
	data['record'] = []
	data['lists'] = {}

def openFile():
	global recFile, data
	try:
		with open(recFile) as json_file:
			data = json.load(json_file)
			# print(str(data))
			json_file.close()
	except:
		initData()

def saveFile():
	global recFile, data
	with open(recFile, 'w') as outfile:
		json.dump(data, outfile, sort_keys=True, indent=4, separators=(',', ': '))

def getSel(self):
	# Only record the first selection region
	# Store as filename:rowStart:colStart-rowEnd:colEnd
	(rowStart, colStart) = self.view.rowcol(self.view.sel()[0].begin())
	(rowEnd, colEnd)	 = self.view.rowcol(self.view.sel()[0].end())
	(colView, rowView)	 = self.view.viewport_position()
	context				 = self.view.substr(self.view.sel()[0])[:COMPARE_LEN]
	return rowStart, colStart, rowEnd, colEnd, (rowView / self.view.line_height()) - rowStart, (colView / self.view.em_width()) - colStart, context

def getFullLocation(self):
	openFile = self.view.file_name()
	if len(openFile) > 0:
		args = getSel(self)
		return Location(openFile, args[0], args[1], args[2], args[3], args[4], args[5], args[6])
	else:
		return None

class RecordLocationOpenFileCommand(sublime_plugin.WindowCommand):
	def run(self, loc, popup_mode = 'Auto'):
		if loc is None:
			return
		if not os.path.exists(loc['file']):
			sublime.status_message("No such file")
			print('No such file: \'', loc['file'],'\'')
			return

		view = self.window.active_view()
		if loc['file'] is not view.file_name():
			sublime.status_message("Opening file...")
			view = self.window.open_file(loc['file'] + ':' + str(loc['rowStart']) + ':' + str(loc['colStart']), sublime.ENCODED_POSITION)

		self.wait_until_open(view, loc, popup_mode)

	def wait_until_open(self, view, loc, popup_mode):
		if view.is_loading():
			sublime.set_timeout(lambda: self.wait_until_open(view, loc, popup_mode), 200)
			return
		sublime.status_message('File opened: '+ view.file_name())
		# split command or selection will not update until scroll moves
		view.run_command('record_location_open_loc', {'loc': loc, 'popup_mode': popup_mode})

class RecordLocationOpenLocCommand(sublime_plugin.TextCommand):
	def run(self, edit, loc, popup_mode = 'Auto'):
		global offsetRow, offsetCol
		self.popup_mode = popup_mode
		pt0 = self.view.text_point(loc['rowStart'], loc['colStart'])
		pt1 = self.view.text_point(loc['rowEnd'], loc['colEnd'])
		select = self.view.sel()
		if select:
			select.clear()
		region = sublime.Region(pt0, pt1)
		region_text = self.view.substr(region)[:COMPARE_LEN]
		if loc['context'] != region_text:
			founds = self.view.find_all(loc['context'], sublime.LITERAL | sublime.IGNORECASE)
			if 0 != len(founds):
				row_offset, col_offset = loc['rowStart'] + offsetRow, loc['colStart'] + offsetCol
				founds_offset = [ abs(row-row_offset) + abs(col-col_offset) for row, col in [self.view.rowcol(pos.a) for pos in founds]]
				# 				  abs((row-row_offset)**2 + (col-col_offset)**2)
				idx_close = founds_offset.index(min(founds_offset))
				offset = founds[idx_close].a - pt0
				row_close, col_close = self.view.rowcol(founds[idx_close].a)
				offsetRow, offsetCol = row_close - loc['rowStart'], col_close - loc['colStart']
				region = sublime.Region(pt0 + offset, pt1 + offset)
				print('region moved (' + str (offsetRow) + ',' + str (offsetCol) + '): \'' + loc['context'] + '\'')
			else:
				print('region text not found: \'' + loc['context'] + '\'')

		select.add(region)
		row_view, col_view = self.view.rowcol(region.a)
		row_view, col_view = row_view + loc['rowViewOffset'], col_view + loc['colViewOffset']
		print ('view: ', [row_view, col_view], 'viewport: ', [col_view * self.view.em_width(), row_view * self.view.line_height()])
		# self.view.set_viewport_position([col_view * self.view.em_width(), row_view * self.view.line_height()])
		svp = self.view.text_to_layout(self.view.text_point(row_view, col_view))
		self.view.set_viewport_position(svp, False)
		print(svp, self.view.viewport_position())
		sublime.status_message("Jumping ~~~ ")
		if 'False' != self.popup_mode:
			self.popup_pos = region.b
			# self.waitUntilStatic(loc['desc'], region, self.view.viewport_position())
			sublime.set_timeout(lambda: self.popup(loc['desc'], region), 00)

	# incase popup being close because scroll move
	def waitUntilStatic(self, desc, region, oldView):
		if self.view.viewport_position() != oldView:
			print('wait view freeze', self.view.viewport_position())
			sublime.set_timeout(lambda: self.waitUntilStatic(desc, region, self.view.viewport_position()), 20)
			return
		sublime.set_timeout(lambda: self.popup(desc, region), 00)

	def popup(self, desc, region):
		if region is not None and not self.view.visible_region().contains(region):
			self.view.show(region, True)
			sublime.set_timeout(lambda: self.waitUntilStatic(desc, region, self.view.viewport_position()), 20)
			return

		print('visible view', self.view.viewport_position(), self.view.is_loading())
		# print('visible region', self.view.visible_region())
		# print('contains region', region)
		# print('popup at ', region.b)
		if desc:
			self.view.show_popup(desc + '<br><a href=edit>edit</a>', sublime.HIDE_ON_MOUSE_MOVE_AWAY, region.b, on_navigate= self.on_navigate)
		else:
			self.view.show_popup('<a href=edit>add desc</a>', sublime.HIDE_ON_MOUSE_MOVE_AWAY, region.b, on_navigate= self.on_navigate)

	def on_navigate(self, value):
		global data, reading_list, reading_list_idx
		print(value, 'input new desc', (str) (data['lists'][reading_list][reading_list_idx]['desc']))
		if 'edit' == value:
			self.view.window().show_input_panel('Description:', str (data['lists'][reading_list][reading_list_idx]['desc']), self.on_done, None, None)

	def on_done(self, value):
		if value is not None:
			data['lists'][reading_list][reading_list_idx]['desc'] = value
			self.popup(value, None)

class RecordLocationCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		global data
		loc = getFullLocation(self)
		if loc:
			data['record'].append(loc.__dict__)
			sublime.status_message("Record location #" + (str) (len(data['record'])))
			# print(data)

	def is_enabled(self):
		return self.view.file_name() is not None

	def is_visible(self):
		return self.is_enabled()

class RecordLocationStopCommand(sublime_plugin.WindowCommand):
	def run(self):
		global data
		self.items = list(data['lists'].keys())
		self.items_name = ['Overwrite ' + i for i in self.items]
		self.items_name.insert(0, 'Create new list')
		self.items_name.insert(1, 'Clear now record')
		self.window.show_quick_panel(self.items_name, self.on_apply)

	def on_apply(self, value):
		global data
		if value == 0:
			self.window.show_input_panel("List name:", '', self.on_done, None, None)
		elif value == 1:
			del data['record']
			data['record'] = []
		elif value != -1:
			self.apply_name(self.items[value-2])

	def on_done(self, value):
		if value is not None:
			self.apply_name(value)

	def apply_name(_, name):
		global data
		data['lists'][name] = data['record']
		del data['record']
		data['record'] = []

	def is_enabled(self):
		global data
		return len(data['record']) > 0

	def is_visible(self):
		return self.is_enabled()

class RecordLocationDelCommand(sublime_plugin.WindowCommand):
	def run(self):
		global data
		self.items = list(data['lists'].keys())
		self.items_name = ['Delete ' + i for i in self.items]
		self.window.show_quick_panel(self.items_name, self.on_done)

	def on_done(self, value):
		global data, reading_list
		if value != -1:
			item = self.items[value]
			if item == reading_list:
				reading_list = None
			del data['lists'][item]

	def is_enabled(self):
		global data
		return len(data['lists']) > 0

	def is_visible(self):
		return self.is_enabled()

class RecordLocationLoadCommand(sublime_plugin.WindowCommand):
	def run(self):
		global data, offsetRow, offsetCol
		offsetRow = 0
		offsetCol = 0
		self.items = list(data['lists'].keys())
		self.items_name = ['Load ' + i for i in self.items]
		self.window.show_quick_panel(self.items_name, self.on_done)

	def on_done(self, value):
		global reading_list, reading_list_idx
		if value != -1:
			reading_list = self.items[value]
			reading_list_idx = -1;
			self.window.run_command("record_location_list")

	def is_enabled(self):
		global data
		return len(data['lists']) > 0

	def is_visible(self):
		return self.is_enabled()

class RecordLocationListCommand(sublime_plugin.WindowCommand):
	def run(self):
		global data, reading_list, reading_list_idx
		if reading_list is None:
			self.window.run_command("record_location_load")
		else:
			self.display_menu_loc_list()

	def display_menu_loc_list(self):
		items_name = [['#' + str(i)+' '+ str(x['context']) ,str(x['desc'])] for i,x in enumerate(data['lists'][reading_list])]
		items_name.append('Goto Top')
		self.window.run_command('hide_overlay')
		self.window.show_quick_panel(items_name, self.display_menu_loc_act, selected_index = reading_list_idx, on_highlight = self.on_loc_list_highlight)

	def on_loc_list_highlight(self, value):
		if -1 == value:
			return
		global reading_list_idx
		if reading_list_idx is not value:
			reading_list_idx = value
			self.window.run_command("record_location_go", {'popup_mode': 'False'})
			self.window.active_view().hide_popup()

	def display_menu_loc_act(self, value):
		if -1 == value:
			return
		self.selec_idx = value
		self.on_loc_list_highlight(value)
		items_name = ['Edit description', 'Edit location', 'Add location before', 'Add location after', 'Duplicate', 'Delete']
		self.window.show_quick_panel(items_name, self.on_loc_act_done)

	def on_loc_act_done(self, value):
		global data, reading_list
		if -1 == value:
			self.display_menu_loc_list()
		elif 0 == value:
			self.window.show_input_panel('Description:', str (data['lists'][reading_list][self.selec_idx]['desc']), self.on_loc_act_edit_done, None, None)
		elif 4 == value:	# Duplicate
			data['lists'][reading_list].insert(self.selec_idx, data['lists'][reading_list][self.selec_idx].copy())
			self.display_menu_loc_list()
		elif 5 == value:	# Delete
			del data['lists'][reading_list][self.selec_idx]
			self.display_menu_loc_list()
		else:
			print('not implement yet')

	def on_loc_act_edit_done(self, value):
		data['lists'][reading_list][self.selec_idx]['desc'] = value
		self.display_menu_loc_act(self.selec_idx)

	def is_enabled(self):
		global data
		return len(data['lists']) > 0

	def is_visible(self):
		global reading_list
		return reading_list is not None

class RecordLocationGoCommand(sublime_plugin.WindowCommand):
	def run(self, popup_mode = 'Auto'):
		global data, reading_list, reading_list_idx
		if reading_list is None:
			self.window.run_command("record_location_load")
		else:
			locs = data['lists'][reading_list]
			reading_list_idx = (reading_list_idx+len(locs)) % len(locs)
			self.window.run_command('record_location_open_file', {'loc': locs[reading_list_idx], 'popup_mode': popup_mode})

	def is_enabled(self):
		global data
		return len(data['lists']) > 0

	def is_visible(self):
		global reading_list
		return reading_list is not None

class RecordLocationNextCommand(sublime_plugin.WindowCommand):
	def run(self):
		global reading_list_idx
		reading_list_idx += 1
		self.window.run_command("record_location_go")

	def is_enabled(self):
		global data
		return len(data['lists']) > 0

	def is_visible(self):
		global reading_list
		return reading_list is not None

class RecordLocationPrevCommand(sublime_plugin.WindowCommand):
	def run(self):
		global reading_list_idx
		reading_list_idx -= 1
		self.window.run_command("record_location_go")

	def is_enabled(self):
		global data
		return len(data['lists']) > 0

	def is_visible(self):
		global reading_list
		return reading_list is not None
