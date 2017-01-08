# Flipnote Player by pbsds

DEBUG = False

import pygame, sys, numpy as np, ConfigParser, time, os, glob, urllib2, random
from scikits.samplerate import resample as SciResample
from Hatenatools import PPM, UGO, NTFT

if "win" in sys.platform:
	from ctypes import windll
	import win32api
	def GetDriveNames():
		bitmask = windll.kernel32.GetLogicalDrives()
		for i, letter in enumerate(map(chr, xrange(ord("A"), ord("Z")+1))):
			if bitmask & (1<<i):
				try:
					label = win32api.GetVolumeInformation("%s:\\" % letter)[0]
				except Exception as i:
					print "win32api error:", i
				if DEBUG: print "win32api:", letter
				yield letter, label
else:
	def GetDriveNames():
		return []
#todo: linux/osx for getting drives

if DEBUG: print "Changing working directory..."
if os.path.exists(os.getcwd()+"/Hatenatools/PPM.py"):
	pass
elif hasattr(sys, 'frozen'):#Compiled archive directory
	os.chdir(os.path.dirname(sys.executable)+"/Hatenatools/PPM.py")
elif os.path.exists(sys.path[0]):#First module folders
	os.chdir(sys.path[0])
elif os.path.exists(os.path.dirname(__file__)+"/Hatenatools/PPM.py"):#Script directory
	os.chdir(os.path.dirname(__file__))

#todo features:
#	- full controlls (volume and stuff)
#	- "file saved" response
#	- framemove tags in hatenatools

class Text():
	def __init__(self):
		self.Fonts = {}
	def Create(self, string, size=9, c=(255,255,255)):
		if size not in self.Fonts:
			self.Fonts[size] = pygame.font.Font("graphics/profontwindows.ttf", size)
		return self.Fonts[size].render(string, False, c)
	def CreateShadowed(self, string, size=9, c1=(255,255,255), c2=(0,0,0)):
		if size not in self.Fonts:
			self.Fonts[size] = pygame.font.Font("graphics/profontwindows.ttf", size)
		
		t1 = self.Fonts[size].render(string, False, c1)
		t2 = self.Fonts[size].render(string, False, c2)
		ret = pygame.surface.Surface((t1.get_width()+1, t1.get_height()+1)).convert()
		ret.set_colorkey((255, 0, 220))
		ret.fill((255, 0, 220))
		
		ret.blit(t2, (0, 1))
		ret.blit(t2, (1, 0))
		ret.blit(t2, (1, 1))
		ret.blit(t1, (0, 0))
		
		return ret
	def CreateSurrounded(self, string, size=9, c1=(255,255,255), c2=(0,0,0)):
		if size not in self.Fonts:
			self.Fonts[size] = pygame.font.Font("graphics/profontwindows.ttf", size)
		
		t1 = self.Fonts[size].render(string, False, c1)
		t2 = self.Fonts[size].render(string, False, c2 )
		ret = pygame.surface.Surface((t1.get_width()+2, t1.get_height()+2)).convert()
		ret.set_colorkey((255, 0, 220))
		ret.fill((255, 0, 220))
		
		ret.blit(t2, (1, 0))
		ret.blit(t2, (0, 1))
		ret.blit(t2, (1, 2))
		ret.blit(t2, (2, 1))
		
		ret.blit(t2, (0, 0))
		ret.blit(t2, (2, 0))
		ret.blit(t2, (0, 2))
		ret.blit(t2, (2, 2))
		
		ret.blit(t1, (1, 1))
		
		return ret
Text = Text()

class player:
	speed2period = {1:1./ 0.5007253346,
	                2:1./ 1.0014343461,
	                3:1./ 2.0027981429,#a bit unsure about this one...
	                4:1./ 4.0057530563,
	                5:1./ 6.0085185544,
	                6:1./12.0173521182,
	                7:1./20.1941106698,#unsure about this one...
	                8:1./30.0250310083}
	TextColor = ((255,255,255), (128,128,128))
	StarColor = ((255,255,255), (255,161,0))
	#60fps for base?
	def __init__(self):
		if not os.path.exists("saved"):
			os.mkdir("saved")
		
		#initalise a pygame window
		#pygame.mixer.pre_init(8192, buffer=512)#lower the buffer to avoid latency
		pygame.mixer.pre_init(44100, buffer=512)#lower the buffer to avoid latency
		pygame.init()
		pygame.font.init()
		pygame.display.set_icon(pygame.image.load("graphics/icon.png"))
		pygame.display.set_caption("Flipnote Player - by pbsds")
		self.window = pygame.display.set_mode((544, 550), pygame.DOUBLEBUF)
		self.browserS = pygame.surface.Surface((512, 384)).convert()
		self.Timer = pygame.time.Clock()
		
		#browser:
		self.browsing = False
		self.dir = None#current directory
		self.history = []#i = (self.dir, labeldir[0])
		self.labeldir = ["Root", Text.CreateShadowed("Root", 9, self.TextColor[0], self.TextColor[1])]#text, surface
		self.files = []#i = (folder(bool), label(spr), label(surface), icon, full path)
		self.scroll = 0; self.prevscroll = 0
		self.ntft = NTFT.NTFT()#reusable :3
		self.tmb = PPM.TMB()#reusable :3
		self.scrollheld = False
		self.scrollerstate = 0
		
		#playback:
		self.ppm = None
		self.ppmRAW = None
		self.frame = -1
		self.tframe = -1
		self.frames = []
		self.sounds = [None, None, None, None]
		self.epoch = None
		self.loop = False
			
		#gfx:
		if 1:
			self.sBG = pygame.image.load("graphics/bg.png").convert()
			self.sBrowserBG = pygame.image.load("graphics/browserbg.png").convert()
			self.sScrollbarBG = pygame.image.load("graphics/scrollbarbg.png").convert()
			self.sIconFolder = pygame.image.load("graphics/folder icon.png").convert()
			self.sIconDrive = pygame.image.load("graphics/drive icon.png").convert()
			self.sIconBase = pygame.image.load("graphics/icon base.png").convert()
			
			self.sLocked = pygame.image.load("graphics/locked.png").convert(); self.sLocked.set_colorkey((0, 255, 33))
			self.sSpinOff = pygame.image.load("graphics/spinoff.png").convert(); self.sSpinOff.set_colorkey((0, 255, 33))
			
			self.sButton = pygame.image.load("graphics/button.png").convert()
			self.sButton.set_colorkey((255, 0, 220))
			self.sButton = (self.sButton.subsurface((0,0,128,48)).convert(), self.sButton.subsurface((128,0,128,48)).convert())
			
			self.sScroller = pygame.image.load("graphics/scroller.png").convert()
			self.sScroller = (self.sScroller.subsurface((0,0,16,64)).convert(), self.sScroller.subsurface((16,0,16,64)).convert(), self.sScroller.subsurface((32,0,16,64)).convert())
			
			self.lPlay = (Text.CreateShadowed("Stop", 9, self.TextColor[0], self.TextColor[1]),
						  Text.CreateShadowed("Play", 9, self.TextColor[0], self.TextColor[1]))
			self.lLoop = (Text.CreateShadowed("Playing once", 9, self.TextColor[0], self.TextColor[1]),
						  Text.CreateShadowed("Looping", 9, self.TextColor[0], self.TextColor[1]))
			self.lScale =(Text.CreateShadowed("Playing once", 9, self.TextColor[0], self.TextColor[1]),
						  Text.CreateShadowed("Looping", 9, self.TextColor[0], self.TextColor[1]),
						  Text.CreateShadowed("Looping", 9, self.TextColor[0], self.TextColor[1]))
			self.lRest = tuple(Text.CreateShadowed(i, 9, self.TextColor[0], self.TextColor[1]) for i in ("Previous frame", "Next frame", "Save Flipnote", "Toggle Scale", "Toggle AdvanceMAME 2X", "Goto Browser", "Goto Player"))
			self.lBrowser = tuple(Text.CreateShadowed(i, 9, self.TextColor[0], self.TextColor[1]) for i in ("Menu", "Back"))
		
		#settings:
		f = open("config.ini", "r")
		self.ini = ConfigParser.ConfigParser()
		self.ini.readfp(f)
		f.close()
		
		self.volume = float(self.ini.getint("settings", "volume"))/1000.
		self.DoScale = self.ini.getboolean("settings", "scale")
		self.MAME = self.ini.getboolean("settings", "AdvanceMameScaler")
		
		self.servers = []#i = (name, address, port, icon)
		for i in xrange(self.ini.getint("servers", "count")):
			self.servers.append(self.ini.get("servers", "server"+str(i+1)).split(":"))
			self.servers[-1][3] = self.CreateIcon(pygame.image.load("graphics/servers/"+self.servers[-1][3])) if self.servers[-1][3] else self.sIconFolder
		
		#metadata:
		pass#todo?
		
		#states:
		self.buttons = [True, True, True, True,
		                True, True, True, True]
		self.labels = [self.lPlay[1], self.lLoop[0], self.lRest[0], self.lRest[1],
		               None, self.lRest[3], self.lRest[4], None]
		self.prevmclick = False
		self.redrawBottomButtons = True
		
		#startup:
		self.GotoBrowser(True)
	def MainLoop(self):
		self.window.blit(self.sBG, (0, 0))
		if self.browsing:
			self.window.blit(self.sScrollbarBG, (528, 72))
			self.window.blit(self.sScroller[0], (528, 72+self.scroll*264/max(((len(self.files)-1)/2-4), 1)))
		
		running = True
		while running:
			#FPS:
			self.Timer.tick(60)
			
			#input:
			events = pygame.event.get()
			
			for i in events:
				if i.type == pygame.QUIT:
					running = False
				if i.type == pygame.MOUSEBUTTONDOWN and self.browsing:
					if i.button == 5:
						if self.scroll < (len(self.files)-1)/2-4:
							if DEBUG: print "down"
							self.scroll += 1
					elif i.button == 4:
						if self.scroll > 0:
							if DEBUG: print "up"
							self.scroll -= 1
			
			self.step()
			
			#push to screen:
			pygame.display.flip()
	def step(self):
		mx, my = pygame.mouse.get_pos()
		mclick = pygame.mouse.get_pressed()[0]
		if mclick and self.prevmclick:
			self.prevmclick = mclick
			mclick = False
		else:
			self.prevmclick = mclick
		
		#bottom buttons:
		for i in xrange(2):
			y = 50*i#pixel offset for buttons/labels
			b = 4*i#self.buttons and self.labels offset
			
			if 445+y<=my<495+y:
				for i in xrange(4):
					updatelabel = False
					
					if 16+i*128<=mx<144+i*128:
						if mclick:
							if not y:
								if i == 0:#play/stop
									if self.playing:
										self.StopPPM()
									else:
										self.PlayPPM()
									updatelabel = True
								if i == 1:#loop toggle:
									self.loop = not self.loop
									self.labels[1] = self.lLoop[1*self.loop]
									updatelabel = True
								if i == 2:#previous frame
									if self.ppm:
										if self.playing:
											self.StopPPM()
											updatelabel = True
										self.frame -= 1
										if self.frame < 0:
											if self.loop:
												self.frame = self.ppm.FrameCount-1
											else:
												self.frame = 0
										self.UpdateFrame()
								if i == 3:#next frame
									if self.ppm:
										if self.playing:
											self.StopPPM()
											updatelabel = True
										self.frame += 1
										if self.frame >= self.ppm.FrameCount:
											if self.loop:
												self.frame = 0
											else:
												self.frame = self.ppm.FrameCount-1
										self.UpdateFrame()
							else:
								if i == 0:#save flipnote
									if self.ppm and self.dir[:7] == "http://":#todo, make a message on screen
										print "saved to", "saved/%i - %s" % (int(time.time()), self.ppm.CurrentFilename)
										f = open("saved/%i - %s" % (int(time.time()), self.ppm.CurrentFilename), "wb")
										f.write(self.ppmRAW)
										f.close()
								if i == 1:#toogle scale
									self.DoScale = not self.DoScale
									if not self.browsing:
										self.UpdateFrame(bg=True)
								if i == 2:#toggle scaler
									self.MAME = not self.MAME
									if not self.browsing:
										self.UpdateFrame()
								if i == 3:#switch view
									if self.browsing and self.ppm:
										self.labels[7] = self.lRest[5]
										pygame.draw.rect(self.window, (128, 192, 6), (528, 72, 16, 328))
										self.browsing = False
										self.UpdateFrame()
									else:
										self.GotoBrowser()
									updatelabel = True
								
							pass#do something
						
						if not self.buttons[i+b]:
							self.buttons[i+b] = True
							updatelabel = True
					else:
						if self.buttons[i+b] == True:
							self.buttons[i+b] = False
							updatelabel = True
					
					if updatelabel or self.redrawBottomButtons:
						self.window.blit(self.sButton[1*self.buttons[i+b]], (16+i*128, 445+y))
						if self.labels[i+b]:
							self.window.blit(self.labels[i+b], (80+i*128-self.labels[i+b].get_width()/2, 445+18+y))
			else:
				if True in self.buttons or self.redrawBottomButtons:
					for i in xrange(4):
						self.window.blit(self.sButton[0], (16+i*128, 445+y))
						if self.labels[i+b]:
							self.window.blit(self.labels[i+b], (80+i*128-self.labels[i+b].get_width()/2, 445+18+y))
						self.buttons[i+b] = False
		self.redrawBottomButtons = False
		
		#playback:
		if self.playing:
			if not self.epoch: self.epoch = time.time()
			
			frame = (time.time() - self.epoch) / self.speed2period[self.ppm.Framespeed]
			if frame >= self.tframe + 1: 
				self.tframe = int(frame)#rounding down
				self.frame = self.tframe % self.ppm.FrameCount
				if DEBUG: print self.tframe, self.frame
				
				if self.frame == 0 and self.tframe <> 0 and not self.loop:
					self.StopPPM()
					self.frame = self.ppm.FrameCount-1
					return
				
				#play sounds:
				if self.frame == 0 and self.sounds[0]:
					self.sounds[0].stop()
					
					self.sounds[0].play()
					if DEBUG: print "play bgm"
				for i, play in enumerate(self.ppm.SFXUsage[self.frame]):
					if play and self.sounds[i+1]:
						self.sounds[i+1].play()
						if DEBUG: print "play sfx", i+1
				
				#draw frame:
				self.UpdateFrame()
		
		#browser:
		elif self.browsing:
			#self.browserS.fill((255, 255, 255))
			self.browserS.blit(self.sBrowserBG, (0, 0))
			
			#top bar:
			for i, label in enumerate(self.lBrowser):
				within = 16<=my<64 and 16+128*i<=mx<144+128*i
				
				self.browserS.blit(self.sButton[1*within], (i*128, 0))
				if not (i==1 and not self.history):
					self.browserS.blit(label, (64+i*128-label.get_width()/2, 18))
				
				if within and mclick:
					if i == 0:
						self.GotoDir(None)
					if i == 1:
						if self.history:
							dir, label = self.history.pop(-1)
							self.GotoDir(dir, label, True)
							if self.history:
								self.history.pop(-1)
			self.browserS.blit(self.labeldir[1], (256+10, 18))
			
			#scrollbar:
			if self.scrollheld or (528<=mx<544 and 72+self.scroll*264/max(((len(self.files)-1)/2-4), 1)<=my<136+self.scroll*264/max(((len(self.files)-1)/2-4), 1)):
				scrollupdate = self.scroll <> self.prevscroll
				if not self.scrollheld:
					self.scrollerstate = 1
					scrollupdate = True
					if mclick:
						self.scrollheld = True
						self.scrollerstate = 2
				
				if self.scrollheld:
					newscroll = int(float(my-104) / (252. / float((len(self.files)-1)/2-4)) + 0.5)
					if newscroll <> self.scroll and 0<=newscroll<=(len(self.files)-1)/2-4:
						self.scroll = newscroll
					
					if not pygame.mouse.get_pressed()[0]:
						self.scrollheld = False
						scrollupdate = True
						self.scrollerstate = 1*(528<=mx<544 and 72+self.scroll*264/max(((len(self.files)-1)/2-4), 1)<=my<136+self.scroll*264/max(((len(self.files)-1)/2-4), 1))
				
				if scrollupdate:
					self.window.blit(self.sScrollbarBG, (528, 72))
					self.window.blit(self.sScroller[self.scrollerstate], (528, 72+self.scroll*264/max(((len(self.files)-1)/2-4), 1)))
					self.prevscroll = self.scroll
			elif self.scrollerstate or self.scroll <> self.prevscroll:
				self.scrollerstate = 0
				
				self.window.blit(self.sScrollbarBG, (528, 72))
				self.window.blit(self.sScroller[self.scrollerstate], (528, 72+self.scroll*264/max(((len(self.files)-1)/2-4), 1)))
				self.prevscroll = self.scroll
			
			#content:
			#for i, (folder, name, label, icon, path) in enumerate(self.files):
			for i in xrange(10):
				if len(self.files) <= i+self.scroll*2: break
				folder, name, label, icon, path = self.files[i+self.scroll*2]
				y = i // 2
				x = i % 2
				
				#todo: scroll
				
				within = 20+256*x<=mx<268+256*x and 76+64*y<=my<140+64*y
				
				if within:
					pygame.draw.rect(self.browserS, (255, 255, 255), (4+256*x, 60+64*y, 248, 64))
				
				self.browserS.blit(icon, (8+256*x, 64+64*y))
				if label:
					if isinstance(label, tuple):
						for i, l in enumerate(label):
							if l:
								self.browserS.blit(l, (88+256*x, 68+16*i+64*y))
					else:
						self.browserS.blit(label, (88+256*x, 84+64*y))
				
				if within and mclick:
					if folder:
						self.GotoDir(path, name)
					else:
						self.PlayPPM(path)
			
			#push to screen:
			if self.browsing:#may have changed
				self.window.blit(self.browserS, (16, 16))
	def UpdateVolume(self):
		for i in self.sounds:
			if i: i.set_volume(self.volume)
	#sub
	def UpdateFrame(self, bg=False):
		#trackbar:
		if self.ppm.FrameCount > 1:
			pygame.draw.rect(self.window, (72, 178, 245), (20, 421, 504*self.frame/(self.ppm.FrameCount-1), 16))
			if not self.playing or self.frame==0:
				pygame.draw.rect(self.window, (245, 130, 6), (20+504*self.frame/(self.ppm.FrameCount-1), 421, 504-504*self.frame/(self.ppm.FrameCount-1), 16))
		else:
			pygame.draw.rect(self.window, (245, 130, 6), (20, 421, 504, 16))
		
		if bg:
			self.window.blit(self.sBG, (16, 16), (16, 16, 16+512, 16+384))
		
		#frame itself
		if self.DoScale:
			if self.MAME:
				self.window.blit(pygame.transform.scale2x(self.frames[self.frame]), (16, 16))
			else:
				self.window.blit(pygame.transform.scale(self.frames[self.frame], (512, 384)), (16, 16))
		else:
			self.window.blit(self.frames[self.frame], (144, 112))
	def GotoDir(self, dir, lappend=None, lforce=False):
		self.history.append((self.dir, self.labeldir[0]))
		self.dir = dir
		self.scroll = 0
		
		if dir==None:
			self.labeldir[0] = "root"
			self.history = []
		elif self.labeldir[0] == "root" or lforce:
			self.labeldir[0] = lappend
		elif lappend:
			self.labeldir[0] = os.path.join(self.labeldir[0], lappend)
		self.labeldir[1] = Text.CreateShadowed(self.labeldir[0], 9, self.TextColor[0], self.TextColor[1])
		
		self.files = []#[i] = (folder(bool), name(spr), label(surface), icon, full path)
		if dir == None:
			if len(glob.glob("saved/*.ppm")):
				self.files.append((True, "saved", Text.CreateShadowed("saved flipnotes", 9, self.TextColor[0], self.TextColor[1]), self.sIconFolder, "saved"))
			
			#self.files.append((True, "local", Text.CreateShadowed("local files", 9, self.TextColor[0], self.TextColor[1]), self.sIconFolder, os.getcwd()))#temp path
			
			
			for i, (letter, label) in enumerate(GetDriveNames()):
				self.files.append((True, "%s:"%letter, Text.CreateShadowed("%s (%s:/)" % (label, letter), 9, self.TextColor[0], self.TextColor[1]), self.sIconDrive, "%s:/"%letter))#temp path
			
			
			for name, address, port, icon in self.servers:
				self.files.append((True, "hatena", Text.CreateShadowed(name, 9, self.TextColor[0], self.TextColor[1]), icon, "prox://%s:%s" % (address, port)))			
			
			#self.files.append((True, "local files", self.LoadIcon(), os.getcwd()))#temp path
			pass
		elif dir[4:7] == "://":
			if dir[:4] == "prox":
				urllib2.install_opener(urllib2.build_opener(urllib2.ProxyHandler({'http': dir[7:]})))
				dir = "http://flipnote.hatena.com/ds/v2-eu/index.ugo"
			
			if dir[:4] == "http":
				ugo = UGO.UGO().Read(self.FetchHatena(dir))
				
				for i in ugo.Items:
					if i[0] == "category":
						link, label, selected = i[1:]
						if not selected and link.split("?")[0][-4:] == ".uls":
							split = link.split("?")
							addr = split[0][:-4]+".ugo" + "?"*(len(split)>1) + "?".join(split[1:])
							
							name = split[0][:-4].split("/")[-1]
							
							self.files.append((True, name, Text.CreateShadowed(label, 9, self.TextColor[0], self.TextColor[1]), self.sIconFolder, addr))#temp path
							
							
					elif i[0] == "button":
						trait, label, link, other, file = i[1:]
						
						if link.split("?")[0][-4:] == ".uls":
							split = link.split("?")
							addr = split[0][:-4]+".ugo" + "?"*(len(split)>1) + "?".join(split[1:])
							
							name = split[0][:-4].split("/")[-1]
							
							if file:
								icon = self.LoadIcon(file[1])#ntft
							else:
								icon = self.sIconFolder
							
							self.files.append((True, name, Text.CreateShadowed(label, 9, self.TextColor[0], self.TextColor[1]), icon, addr))#temp path
						elif link[-4:] == ".ppm":
							icon = self.LoadIcon(file[1])#tmb
							
							username = Text.CreateShadowed(u"submitted by "+self.tmb.Username, 9, self.TextColor[0], self.TextColor[1])
							filename = Text.CreateShadowed(file[0][:-4],      9, self.TextColor[0], self.TextColor[1])
							stars    = Text.CreateShadowed(other[0] + " stars",     9, self.StarColor[0], self.StarColor[1])
							
							self.files.append((False, "flipnote", (filename, username, stars), icon, link))
		else:
			folders = []
			files = []
			for i in glob.glob(os.path.join(dir, "*")):
				if os.path.isdir(i):
					folders.append(i)
				elif i[-4:] == ".ppm":
					files.append(i)
			
			folders.sort(key=lambda x: x.lower())
			for i in folders:
				name = os.path.basename(i)
				self.files.append((True, name, Text.CreateShadowed(name, 9, self.TextColor[0], self.TextColor[1]), self.sIconFolder, i))
			
			files.sort()
			for i in files:
				name = os.path.basename(i)
				
				f = open(i, "rb")
				icon = self.LoadIcon(f.read())
				f.close()
				
				username = Text.CreateShadowed(u"submitted by "+self.tmb.Username, 9, self.TextColor[0], self.TextColor[1])
				filename = Text.CreateShadowed(self.tmb.CurrentFilename[:-4],           9, self.TextColor[0], self.TextColor[1])
				
				self.files.append((False, name, (username, filename), icon, i))
	#public
	def PlayPPM(self, file=None, path=True):
		if file:
			if path:
				if file[:7] == "http://":
					self.LoadPPM(self.FetchHatena(file))
					self.labels[4] = self.lRest[2]
				else:
					f = open(file, "rb")
					self.LoadPPM(f.read())
					f.close()
					self.labels[4] = None
				self.redrawBottomButtons = True
			else:
				self.LoadPPM(file)
		else:
			if self.browsing and not self.ppm:
				return
		
		if not self.DoScale:
			self.window.blit(self.sBG, (16, 16), (16, 16, 16+512, 16+384))
		
		self.browsing = False
		pygame.draw.rect(self.window, (128, 192, 6), (528, 72, 16, 328))
		self.labels[7] = self.lRest[5]
		
		
		
		self.frame = -1
		self.playing = True
		self.labels[0] = self.lPlay[0]
		self.redrawBottomButtons = True
	def StopPPM(self):
		self.playing = False
		self.epoch = None
		#self.frame = -1
		self.tframe = -1
		for i in self.sounds:
			if i: i.stop()
		self.labels[0] = self.lPlay[1]
		self.redrawBottomButtons = True
	def GotoBrowser(self, root = False):
		self.StopPPM()
		self.browsing = True
		if self.ppm: self.labels[7] = self.lRest[6]
		
		self.window.blit(self.sScrollbarBG, (528, 72))
		self.window.blit(self.sScroller[0], (528, 72+self.scroll*264/max(((len(self.files)-1)/2-4), 1)))
		
		if root: self.GotoDir(None)
	#internal
	def LoadPPM(self, data):
		self.clean()
		
		self.ppm = PPM.PPM().Read(data, DecodeThumbnail=True, ReadFrames=True, ReadSound=True)
		if not self.ppm:
			return False
		self.ppmRAW = data
		
		if DEBUG: print "speed",self.ppm.Framespeed, "with bgm recorded at",self.ppm.BGMFramespeed
		if DEBUG: print self.ppm.FrameCount, "frames"
		
		self.frames = []
		for i in xrange(self.ppm.FrameCount):
			frame = self.ppm.GetFrame(i)
			
			#convert from 2d uint32 RGBA to 3d uint8 RGB:
			frame3d = np.zeros((256, 192, 3), dtype=">u1")
			frame3d[:,:,0] = frame >> 24 #red
			frame3d[:,:,1] = frame >> 16 & 0xFF#green
			frame3d[:,:,2] = frame >> 8 & 0xFF#blue
			#frame3d[:,:,3] = frame &0xFF#alpha
			
			self.frames.append(pygame.surfarray.make_surface(frame3d).convert())
		
		
		for i in xrange(4):
			data = self.ppm.GetSound(i)
			if data:
				if DEBUG: print "sound index",i,len(data),"frames"
				
				dataNP = np.fromstring(data, dtype=np.int16)
				ratio =  1. / 8192.*44100. / self.speed2period[self.ppm.BGMFramespeed] * self.speed2period[self.ppm.Framespeed]
				#newsize =  float(dataNP.shape[0]) * ratio
				
				if DEBUG: print dataNP.shape[0], "to", float(dataNP.shape[0]) * ratio, "@", ratio
				
				resampled = SciResample(dataNP, ratio, "sinc_fastest")#dtype here is now float32
				
				#scale down again:
				resampled = resampled * (float(dataNP.max())/float(resampled.max()))
				
				#convert to sterio and pass to pygame:
				stereo = np.zeros((resampled.shape[0],2), dtype=np.int16)
				stereo[:,0] = resampled
				stereo[:,1] = resampled
				self.sounds[i] = pygame.mixer.Sound(buffer(stereo.tostring()))
		self.UpdateVolume()		
		
		self.loop = self.ppm.Looped
		self.labels[1] = self.lLoop[1*self.ppm.Looped]
	def clean(self):#remove current loaded ppm
		self.StopPPM()
		
		#pygame:
		for i in xrange(len(self.frames)-1,-1,-1):
			del self.frames[i]
		for i in xrange(4):
			if self.sounds[i]:
				del self.sounds[i]
				self.sounds.insert(i, None)
		
		del self.ppm, self.ppmRAW
		self.ppm = None
		self.ppmRAW = None
	def LoadIcon(self, data, locked=False, spinoff=False, gettmb=True):#returns it
		if data[:4] == "PARA":#flipnote
			self.tmb.Read(data, True)
			img = self.tmb.GetThumbnail(force=True)
			
			if gettmb:
				locked = self.tmb.Locked
				if not (self.tmb.OriginalAuthorID == self.tmb.EditorAuthorID == self.tmb.PreviousEditAuthorID):
					spinoff = True
		else:#NTFT
			self.ntft.Read(data, (32, 32))
			img = self.ntft.Image
		
		#convert to surface:
		img3d = np.zeros((img.shape[0], img.shape[1], 3), dtype=">u1")
		img3d[:,:,0] = img >> 24 #red
		img3d[:,:,1] = img >> 16 & 0xFF#green
		img3d[:,:,2] = img >> 8 & 0xFF#blue
		#img3d[:,:,3] = img & 0xFF#alpha
		
		surf = pygame.surfarray.make_surface(img3d[:,:,:3])
		
		if data[:4] <> "PARA":#ntft alpha:
			surf = surf.convert_alpha()
			a = pygame.surfarray.pixels_alpha(surf)
			a[:,:] = img & 0xFF#alpha
			del a
		del img, img3d
		
		if locked:
			surf.blit(self.sLocked, (47, 30))
		if spinoff:
			surf.blit(self.sSpinOff, (2, 34))
		
		return self.CreateIcon(surf)
	def CreateIcon(self, surface):
		out = self.sIconBase.copy()
		out.blit(surface, (4+32-surface.get_width()/2, 4+24-surface.get_height()/2))
		return out
	def FetchHatena(self, addr):
		if DEBUG: print "hatenafetch:", addr
		
		#sudomemo fix. Sudomemo blocks requests with user-agents and requires each session to have a unique SID
		if addr == "http://flipnote.hatena.com/ds/v2-eu/index.ugo":
			self.SID = 'pbsdsFlipnotePlayer%s' % "".join((chr(random.randrange(ord("A"), ord("Z")+1) + random.choice((0, ord("a")-ord("A")))) for _ in xrange(21)))
			if DEBUG: print "generated SID:", self.SID
		urllib2._opener.addheaders = []
		
		request = urllib2.Request(addr, headers={'x-dsi-sid': self.SID})		
		
		resp = urllib2.urlopen(request)
		
		data = resp.read()
		
		if 0 and addr.split("/")[-1].split("?")[0][-4:] == ".ugo":
			
			print "writing ugo...",
			f = open("hatenafetch/"+addr.split("/")[-1].replace("?", "."), "wb")
			f.write(data)
			f.close()
			
			print "writing ugoxml..."
			name = addr.split("/")[-1].split("?")[0]+ "xml" + "."*(len(addr.split("/")[-1].split("?")) > 1) + ".".join(addr.split("/")[-1].split("?")[1:])
			UGO.UGO().Read(data).WriteXML(xmlname="hatenafetch/"+name, folder=("%s embedded" % name))
			
			print "done"
		
		return data
	#events:
	def save(self):
		self.ini.set("settings", "volume", str(int(self.volume*1000+0.5)))
		self.ini.set("settings", "scale", str(self.DoScale))
		self.ini.set("settings", "AdvanceMameScaler", str(self.MAME))
		
		f = open("config.ini", "w")
		self.ini.write(f)
		f.close()

def main():
	program = player()
	
	#if "opened with" a ppm file:
	if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
		program.GotoDir(os.path.dirname(sys.argv[1]))
		program.PlayPPM(sys.argv[1])
		
	program.MainLoop()#blocking
	
	print "ech"
	
	program.save()

def excepthook(type, value, traceb):
	import traceback
	class dummy:
		buff = ""
		def write(self, data):
			self.buff += data
	
	dummyf = dummy()
	traceback.print_exception(type, value, traceb, file=dummyf)
	f = open("error.txt", "w")
	f.write(dummyf.buff)
	f.close()
	print dummyf.buff
	print "Error message written to error.txt"
	sys.exit()
if(__name__ == '__main__'):
	sys.excepthook = excepthook
	main()
