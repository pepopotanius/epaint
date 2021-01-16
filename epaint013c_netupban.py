#! python3
# coding: utf-8
# 画像読み込んで、拡大機能付スケッチできる
# 
# 
# 20201228 ver000 easypaint作成開始。
# 20201229 ver001 scrollviewに大きな画像を見て表示してスクロールを実装。
# 20201231 ver002 bottonmenu追加。座標など表示追加。
# 20210101 ver003 pathを別クラスで作成。touchイベントは　scrollviewとpathで競合する。最前面のみ受け取る。
# 20210101 ver004 btn_lock他改。touch競合させないためにscvとpvのタッチ有効を切り替える+フレームそろえてpvの座標補正。
# 20210101 ver005 path作画に色と幅を反映させた。pathの作画位置は左上に飛ぶまま。loadは何バージョンか前に実装済み。
# 20210102 ver006 path作画がスクロールしても左上に飛ばないように修正。pvにoffsetを流し込む処理をいれた。
# 20210102 ver007 save作成。
# 20210103 ver008 zoom作成。zoom時の中心位置が左上の少し上と変。左上付近で作画すると全面塗りのエラーが出る。
# 20210105 ver009 タイトルに画像サイズと倍率とファイル名用引数又はepaintを表示。path描画おかしいの修正。
# 20210105 ver010 save画像が倍率で2倍化するのを修正。save完了を表示。
# 20210106 ver011b b版。undo実装。しかし、写真3200x2400サイズでは作画が遅い。
# 20210107 ver012c c版。動作速度改善やundoの太さ等初期化されるバグ修正。コードの注記と旧コード整理。
# 20210110 ver013c c版。scroll後のzoomで作画位置ズレるバグ修正。ボタン位置修正。
# 残
# 
# 読み込んだ写真ファイル名の取得は、断念。中間ファイル名しか取得できない。元ファイル名＋アルファで保存したい。
# QRコードを埋め込んで、元ファイル名渡すのは断念。QRコードのデコードがカメラ経由しかない。
# 画像にステガノグラフィー埋込で元ファイル名を渡すのは、動作スピードからイマイチ。スレッドを分けて作業する？ 
# 
# 

import ui, os, sys, photos, scene
import Image, io
import datetime


def pil2ui(imgIn): # pil(jpg) => ui(PNG) pilとios(ui)の使う画像データは異なるので　変換が必要。今回はpil→uiに変換してる。imgIn=pil
	with io.BytesIO() as bIO: # pilの画像データをiosのuiで使える画像データに変換する。import io必要
		imgIn.save(bIO, 'PNG')
		imgOut = ui.Image.from_data(bIO.getvalue())
	del bIO
	return imgOut

########################################
#手描きを画面に作画。SCROLLVIEWとは競合するので、別classにする必要がある。最前面のみ動く。
class PathView (ui.View):
    def __init__(self):
        #self.frame = frame
        self.flex = 'WH'
        self.frame=(0,40,1000,680)
        self.color = 'red'
        self.path_width = 3
        self.path_color = 'red'
        
        self.action = None
        self.touch_enabled = True
        self.path = None
        self.paths = []
        self.bpath = None
        self.bpaths= []
        
        self.scvoffset_x = 0
        self.scvoffset_y = 0
        self.scvrate = 1.0
        self.image = None
        self.base_image = None
        self.image_w = 256
        self.image_h = 256
        
        
    def touch_began(self, touch):
        x, y = touch.location
        x2 = (self.scvoffset_x + x)/self.scvrate
        y2 = (self.scvoffset_y + y)/self.scvrate
        
        print('touch_began x  '+str(x)+' y  '+str(y))
        print('           x2:'+str(x2)+' y2:'+str(y2)+' rate'+str(self.scvrate))
        print('scv offset x'+str(self.scvoffset_x)+' y'+str(self.scvoffset_y))
        
        self.path = ui.Path()#画面描画用
        self.path.line_width = self.path_width#この一文は幅の初期値設定のみ。固定値でＯＫ。
        self.path.line_join_style = ui.LINE_JOIN_ROUND
        self.path.line_cap_style = ui.LINE_CAP_ROUND
        self.path.line_width = 3#
        self.path.move_to(x, y)
        
        self.bpath=ui.Path()#画像に描画用
        self.bpath.line_width = self.path_width#この一文は幅の初期値設定のみ。固定値でＯＫ。
        self.bpath.line_join_style = ui.LINE_JOIN_ROUND
        self.bpath.line_cap_style = ui.LINE_CAP_ROUND
        self.bpath.line_width = 0#画面上に描画しない様に幅０とする。
        self.bpath.move_to(x2, y2)
        
    
    def touch_moved(self, touch):
        x, y = touch.location
        x2 = (self.scvoffset_x + x)/self.scvrate
        y2 = (self.scvoffset_y + y)/self.scvrate
        
        #print('touch_moved x ;'+str(x)+' y'+str(y))
        #print('touch_moved x2;'+str(x2)+' y'+str(y2))
        
        self.path.line_to(x, y)#これ実行しないと画像に描画されない。が、実行すると画面に一時的に描画される。
        self.bpath.line_to(x2,y2)#画面描画用と画像描画用両方実行し、画像描画用を幅０で非表示。描画時に幅を渡す。
        self.set_needs_display()
    
    def touch_ended(self, touch):
        print('touch_ended')
        
        #bpathsにpathを保存して、undo実装に利用する。pathは経路のみなので、線色と線幅も記録する。
        self.bpaths.append((self.bpath, (int(self.image_w), int(self.image_h)), self.path_color,int(self.path_width)))
        # viewにactionを設定して、描画の関数を呼ぶ。acionに登録しないと上位クラスの関数path_actionを呼べなかった。
        if callable(self.action): # callableは、関数が実行可能かを調べる。要らないかも？
            self.action(self)#pvのactionに設定しているので、path_actionを呼んでいる。
        # pathを１筆毎に初期化。
        self.path = None
        self.bpath = None
        self.set_needs_display()
    
    #この関数で、タッチを画面に描画している。
    def draw(self):
        if self.path:
            self.path.stroke()
            self.bpath.stroke()
    
    #undoを実現する時にline_widthをメインプログラム側でいじれなかったのでpvインスタンスで実行
    def pv_bpath_undo(self):
        print('pv_path_undo')
        bpath = None
        if callable(self.action):
            self.action(self)#pvのactionを呼んでいる。path_action
        bpath = None
    
    



########################################
# メインプログラム　
class epaint(ui.View):
	def __init__(self,filename1):
		self.name='easy paint'#viewの名前表示。後程ここに、倍率とxy座標uiを表示する。
		self.btn_w=100#ボタンの幅
		self.btn_h=40 #ボタンの高さ
		self.filename1 = filename1
		
		self.path_color = 'red'
		self.path_width = int(6)
		self.scvoffset_x = int(0)#元画像に対する描画面左上の原点位置
		self.scvoffset_y = int(0)#元画像に対する描画面左上の原点位置
		self.scvrate = float(1.0)#元画像に対する描画面の倍率
		self.scvrate0= float(1.0)#zoom前の描画倍率保管用
		self.image_w,self.image_h=int(0),int(0)#元画像の幅と高さ
		self.pathimage_x,self.pathimage_y=int(0),int(0)#元画像のパス座標
		self.pathscv_x,pathscv_y=int(0),int(0)#描画面のパス座標
		self.paths = []#pathを配列にして保管する。（undo用）
		self.path=None
		
		self.base_image = ui.Image.named('test:Peppers')#元画像
		self.image_w,self.image_h = self.base_image.size#元画像の幅と高さpil.sizeメソッド
				
		w,h = ui.get_screen_size()#画面サイズを取得。xとかクラス名除く部分。
		self.scr_w,self.scr_h = w,h #全画面の幅と高さ
		
		self.biv = ui.ImageView()#base image view元画像のビュー
		self.biv.frame = (0, 0,self.image_w,self.image_h)#元画像のサイズを取得。左上の座標と右下の座標
		#                                  左上絶対座標x,左上絶対座標y,右下x絶対座標,右下y絶対座標
		#　ui座標　左上を原点に右下に向かって座標が増える。
		#　scene座標　左下を原点に右上に向かって座標が増える。いわゆる普通のxy座標と同じ。
		#

		self.biv.image = self.base_image
		self.biv.bg_color = 'red'
		self.biv.center = (128,128)#viewの中心をどの座標に表示するかを指定。test画像が256x256なので仮に128とした。
		self.biv.transform = ui.Transform.scale(1,1)#bivに表示する画像の倍率を指定。x方向とy方向で指定。
		#self.biv.image = ui.Image.from_data(pil2ui(photos.pick_image()))#動かない。イメージの形式が違う？
		self.scv = ui.ScrollView()
		#フレーム(実際に表示すrscrollviewの窓サイズ)の幅を宣言
		self.scvframesize=(0,self.btn_h+3,self.scr_w,self.scr_h-self.btn_h-80)
		self.scv.frame = self.scvframesize#(0,self.btn_h+3,self.scr_w,self.scr_h-self.btn_h-80)
		self.scv.content_size = (self.image_w,self.image_h)#元画像を入れる枠のサイズを宣言
		#self.scv.flex='WH' #
		self.scv.scroll_enabled = False#False # スクロールがTrue有効=動く・False無効=停止。デフォルトTrue
		self.scv.touch_enabled = False#Falseタッチイベントを受け取らない。下のviewにタッチ渡す。
		#Trueタッチイベント受け取る。下のviewにタッチ渡さない。
				
		self.scv.add_subview(self.biv)#scvにbivを入れる事で　scrollviewの元画像contentsに代入した。
		self.add_subview(self.scv)#selfにscvを入れる事で表示させるのはscvと宣言した
		
		
		self.btnscv = ui.ScrollView()#menu buttonのscrollviewを作成
		self.btnscv.background_color = '#d9dcff'#薄紫色
		self.btnscv.frame = (0,0,self.scr_w,self.btn_h)
		self.btnscv.content_size = (1300,self.btn_h)
		self.btnscv.flex = 'W'#幅方向にのみフィックス
		self.add_subview(self.btnscv)
		
		#menu buttonを登録。同じ項目の繰り返しは下記の関数config_buttonで作っている。
		#config_button(button, name, frame, title)
		self.scv_btn_lock = ui.Button()
		self.config_button(self.scv_btn_lock, 'btn_lock',(5*self.btn_w,0,self.btn_w,self.btn_h), 'Lock')
		self.scv_btn_load = ui.Button()
		self.config_button(self.scv_btn_load, 'btn_load',(0*self.btn_w,0,self.btn_w,self.btn_h), 'Load')
		self.scv_btn_save = ui.Button()
		self.config_button(self.scv_btn_save, 'btn_save',(1*self.btn_w,0,self.btn_w,self.btn_h), 'Save')
		self.scv_btn_undo = ui.Button()
		self.config_button(self.scv_btn_undo, 'btn_undo',(4*self.btn_w,0,self.btn_w,self.btn_h), 'Undo')
		self.scv_btn_color = ui.Button()
		self.config_button(self.scv_btn_color, 'btn_color',(2*self.btn_w,0,self.btn_w,self.btn_h), 'Color')
		self.scv_btn_path_width = ui.Button()
		self.config_button(self.scv_btn_path_width, 'btn_path_width',(3*self.btn_w,0,self.btn_w,self.btn_h), '-')#線の幅を指定するボタンなので　title無
		self.scv_btn_zoomin = ui.Button()
		self.config_button(self.scv_btn_zoomin,'btn_zoomin',(6*self.btn_w,0,self.btn_w,self.btn_h),'Zin')
		self.scv_btn_zoomout = ui.Button()
		self.config_button(self.scv_btn_zoomout,'btn_zoomout',(7*self.btn_w,0,self.btn_w,self.btn_h),'Zout')

		self.lock_switch = 'lock'
		self.colors = ['white', 'grey', 'red', 'green', 'blue', 'cyan', 'magenta', 'yellow']
		self.color_nr = 2    #red　線の初期色を指定
		self.path_widths = [3, 6, 12, 24]
		self.path_w_nr = 1	    #6 線の幅が　何ｐかを指定
		self.scv_btn_color.tint_color = self.colors[self.color_nr]

		

		#タッチを作画に渡すに必要(画面に作画まで実施)しかし、viewが最手前のみtouchイベントを受け取る。
		#つまり、作画とスクロールビューは両立できない。（最前面を入れ替える事で可能.タッチ有効の切替でも可能）
		self.pv = PathView()#(frame=self.bounds)
		self.pv.frame = self.scvframesize#(0,self.btn_h,self.scr_w,self.scr_h-self.btn_h)
		self.pv.action = self.path_action
		self.pv.color=self.colors[self.color_nr]
		self.pv.path_width = self.path_widths[self.path_w_nr]
		self.pv.scvoffset_x = self.scvoffset_x
		self.pv.scvoffset_y = self.scvoffset_y
		self.pv.scvrate = self.scvrate
		self.add_subview(self.pv)
		
		self.path_width_change()
		self.image = None
		self.set_btn_actions()#btnにactionを追加。（関数読込後しか登録できないので、後追加とした）
		#
		self.present('fullscreen')


	###############################
	#btn click no action def
	def btn_lock(self,sender):
		self.logp(sender,'btn_lock')
		#scrollviewの要素修正して、スクロールのロック・解除を
		#self.scv.scroll_enabld = True#False # スクロールがTrue有効=動く・False無効=停止。デフォルトTrue
		if self.lock_switch == 'lock':
			print('btn_lock  to scroll')
			self.lock_switch = 'scroll'
			self.scv.scroll_enabled = True
			self.scv_btn_lock.title = 'scroll'
			#self.pv.send_to_back()#ビューを背面に移動する。（手前のビューが不透明だと見えなくなる）
			self.scv.touch_enabled = True#Falseタッチイベントを受け取らない。下のviewにタッチ渡す。
			self.pv.touch_enabled = False#Falseタッチイベントを受け取らない。下のviewにタッチ渡す。
		else:
			print('btn_lock  to lock')
			self.lock_switch = 'lock'
			self.scv.scroll_enabled = False
			self.scv_btn_lock.title = 'lock'
			#self.scv.send_to_back()#viewを背面に送る。これをすると画面が上面のviewの下に隠れる。
			self.scv.touch_enabled = False#Falseタッチイベントを受け取らない。下のviewにタッチ渡す。
			self.pv.touch_enabled = True#Falseタッチイベントを受け取らない。下のviewにタッチ渡す。

			self.scvoffset_x,self.scvoffset_y = self.scv.content_offset
			self.pv.scvoffset_x = self.scvoffset_x#pvの中に現在のscvoffsetを流し込む。
			self.pv.scvoffset_y = self.scvoffset_y
			
	
	def btn_load(self,sender):
		print('btn_load')
		self.scvrate = 1
		self.scvrate0 =1

		self.base_image = ui.Image.from_data(photos.pick_image(raw_data=True))
		self.image_w,self.image_h = self.base_image.size#元画像の幅と高さpil.sizeメソッド
		
		self.pv.image_w , self.pv.image_h = self.image_w , self.image_h
		
		self.biv.frame = (0, 0,self.image_w,self.image_h)#元画像のサイズにbivを変更
		self.scv.content_size = (self.image_w,self.image_h)#元画像を入れる枠のサイズを宣言
		w,h = ui.get_screen_size()#画面サイズを取得。xとかクラス名除く部分。
		self.scr_w,self.scr_h = w,h #全画面の幅と高さ
		
		self.scvrate0 = self.scvrate #*2
				
		self.biv.image = self.base_image#元画像をbivに代入。
		
		self.zoom_set(sender)

		#titleに画像サイズと倍率を表示
		self.name ='Size:' + str(int(self.image_w)) + ', ' + str(int(self.image_h))+' rate:'+str(self.scvrate)+' '+self.filename1

		self.set_needs_display()
					
	def btn_save(self,sender):
		print('btn_save')
		saveimage0 = self.ui2pil(self.biv.image)
		
		nitiji_now = datetime.datetime.now() # 現在日時の取得
		file_nitiji = nitiji_now.strftime("%Y%m%d_%H%M%S" )#pillowはファイル名に全角は使えない。
		# datetime関数から日時を取り出して、表示する文字の変数に代入。ファイル名にいきなり入れると処理落ちする事がある
		filename = file_nitiji+'.jpg'
		print(str(self.image_w)+' , '+str(self.image_h))
		#pil risize　int必須。ANTIALIASは、性能重視で遅い。
		saveimage = saveimage0.resize((int(self.image_w),int(self.image_h)),Image.ANTIALIAS)#for PIL
		#zoom関係なく、ｘｙ各々２倍になるので、元のサイズに縮小している。
		saveimage.save(filename, quality=95, optimize=True, progressive=True)#for PIL
		# カメラロールに保存する前にpyのフォルダに画像を保存する必要がある。
		filename2 = 'MemoCamera'+str(self.filename1)+str(file_nitiji)+'Draw.jpg'
		#filename1=nyuuryoubunn クラス呼出時のコンストラクタに追加した引数
		os.rename(filename,filename2)#pillowの代わりに全角ファイル名を作成
		#print('Draw_filename2:',filename2)
		photos.create_image_asset(filename2) # カメラロールへの保存。
		# ファイル名は以前に保存した画像ファイルへのパス。保存名ではない。
		
		#file deleate
		os.remove(filename2) 
		# pyフォルダに生成されたJPEGを消さないと、最初のファイルのタイムスタンプが
		# 写真のexifデータに継承され続ける為、pyフォルダのjpgは毎回消す。
			#titleに画像サイズと倍率を表示
		self.name ='save success'		
		
		#self.close() #保存したらスクリプトを閉じたいときに有効化する。
				

	def btn_undo(self, sender):
		print('btn_undo')
		self.path_undo(sender)
		
		self.set_needs_display()

	def btn_color(self, sender):
		if self.color_nr < len(self.colors) - 1:
			self.color_nr += 1
		else:
			self.color_nr = 0
		self.scv_btn_color.tint_color = self.colors[self.color_nr]
		self.path_color = self.colors[self.color_nr]
		self.pv.path_color = self.path_color
		self.path_width_change()

	def btn_path_width(self, sender):
		if self.path_w_nr < len(self.path_widths) - 1:
			self.path_w_nr += 1
		else:
			self.path_w_nr = 0
		self.path_width = self.path_widths[self.path_w_nr]
		self.pv.path_width = self.path_width
		self.path_width_change()

	def btn_zoomin(self,sender):
		print('btn_zoomin')
		self.scvrate0= self.scvrate
		self.scvrate = self.scvrate * 2
		self.zoom_set(sender)
		self.logp(sender,'zoomin')
		
				
	def btn_zoomout(self,sender):
		print('btn_zoomout')
		self.scvrate0= self.scvrate
		self.scvrate = self.scvrate * 0.5
		self.zoom_set(sender)
		self.logp(sender,'zoomout')
		

###############################						
# sub tool

	def pil2ui(imgIn): # pil(jpg) => ui(PNG) pilとios(ui)の使う画像データは異なるので　変換が必要。今回はpil→uiに変換してる。imgIn=pil
		with io.BytesIO() as bIO: # pilの画像データをiosのuiで使える画像データに変換する。import io必要
			imgIn.save(bIO, 'PNG')
			imgOut = ui.Image.from_data(bIO.getvalue())
		del bIO
		return imgOut
	
	#from pythonista forum
	def ui2pil(self, image):
		mem = io.BytesIO(image.to_png())
		out = Image.open(mem)
		out.load()
		mem.close()
		return out
	
	
	# ボタンをまとめて設定する関数。同じ属性の繰り返し登録なので　関数化してる。
	def config_button(self,button,name,frame,title):
		button.name = name
		button.frame = frame
		button.title = title
		button.border_width = 1
		button.corner_radius = 2
		button.border_color = 'blue'
		button.font = ('<system-bold>',25)
		#button.action = name#ボタン押した時の関数はボタン名称と同じにした。
		#しかし、コールする関数を先に読み込む必要があるので、ここでは追加できない。後で別の関数で追加。
		self.btnscv.add_subview(button)#menu buttonのscrollview=btnscvにボタンを元ビューとして代入。

	#ボタンのアクションは、アクションの関数を登録していないと宣言できないので、最後に登録する
	def set_btn_actions(self):
		for subview in self.btnscv.subviews:#ボタンの入っているviewを指定する
			if isinstance(subview, ui.Button):
				subview.action = getattr(self, subview.name)

	# imageviewに、加工後の写真を表示する。
	def imgv_pick():
		imgIn = photos.pick_image()
		imggg = pil2ui(imgIn) # 下記でpil→uiに画像形式変換してる。
		#sender.superview['photo1'].image = imggg # imegeviewのphoto_nowにios(ui)形式画像を渡して、反映。
		return imggg
		# ウィンドウサイズに画像を適当にfitさせてくれる。
		
##############################
# draw tool
	#path_width buttonの線幅画像を変更する
	def path_width_change(self):
		with ui.ImageContext(self.btn_w, self.btn_h) as ctx:
			ui.set_color(self.colors[self.color_nr])
			path = ui.Path()
			path.line_width = self.path_widths[self.path_w_nr]
			path.line_join_style = ui.LINE_JOIN_ROUND
			path.line_cap_style = ui.LINE_CAP_ROUND
			path.move_to(20,20)
			path.line_to(80,20)
			path.stroke()
			image = ctx.get_image()

			#background_imageは、ボタンの背景画像を入れるuiメソッド
			self.scv_btn_path_width.background_image = image
			#線幅のボタンに線色と線幅を反映した画像を背景画像として入れている。


		
	#特に意味は無い。
	def layout(self):
		pass
		
	#bivに座標変換したbpathでbivに作画	
	def path_action(self, sender):
		#path = sender.path
		bpath= sender.bpath#pvなどのインスタンス内init外の属性にアクセスする時に必要。関数にもsender要る。
		#　今回の場合「インスタンス内init外の属性」=self.pv.bpath.line_width .但し、pvのactionに登録無いとエラー。
		
		old_img = self.biv.image
		width, height = self.image_w,self.image_h		
		#bivのサイズ取得だと、画像縮小時に画像の左上部分が切り取られる為、使えない。
		self.logp(sender,'path_action')
		
		#pathをイメージに作画している。w hは、作画範囲なのでbase_imgeのサイズ。zoomされるbivサイズではない。
		with ui.ImageContext(width, height) as ctx:
			if old_img:
				old_img.draw()
			self.pv.bpath.line_width = self.path_width#線の幅を反映させる
			ui.set_color(self.path_color)#pathの作画色を反映させる	
			bpath.stroke()
			self.biv.image = ctx.get_image()

		
	def path_undo(self,sender):
		#bpath= sender.bpath
		last_path_color = self.path_color
		last_path_width = self.path_width
		
		#bpathsリストの個数をカウントしている。undoで再度全bpathを再作画する為。
		path_count = len(self.pv.bpaths)
		#print(self.pv.bpaths)
		
		width, height = self.image_w,self.image_h
		#print('w h '+str(width)+' , '+str(height))
		
		if path_count > 0:
			self.pv.bpaths.pop()#最後の要素を削除する
			path_count -= 1
			self.biv.image = self.base_image # bivの画像をbpath無に戻す。
			for i in range(0, path_count):#bpathを最初から１つ前のbpathまで再作画しなおす。
					self.path_width = self.pv.bpaths[i][3]#self.path_width#線の幅を反映させる
					self.path_color = self.pv.bpaths[i][2]#
					self.pv.bpath = self.pv.bpaths[i][0]
					self.pv.pv_bpath_undo()#線幅を反映させる為にpv中でbpthを生成させている

			self.path_color = last_path_color
			self.path_width = last_path_width
			
			self.set_needs_display()		
		

	def zoom_set(self,sender):
		scvw,scvh = self.scr_w,self.scr_h-self.btn_h-80#scvのサイズを取得
		self.scvoffset_x,self.scvoffset_y = self.scv.content_offset#scvの左上原点のbiv中の位置
		#scv offsetを拡大縮小した時の位置近くに移動させる
		newx=self.scvoffset_x * self.scvrate / self.scvrate0
		newy=self.scvoffset_y * self.scvrate / self.scvrate0		
		
		self.biv.frame = (0,0,self.image_w*self.scvrate,self.image_h*self.scvrate)
		self.scv.content_size = (self.image_w*self.scvrate,self.image_h*self.scvrate)#元画像を入れる枠サイズ

		self.scvoffset_x,self.scvoffset_y = self.scv.content_offset#scvの左上原点のbiv中の位置		
		self.pv.scvoffset_x = self.scvoffset_x#pvの中に現在のscvoffsetを流し込む。
		self.pv.scvoffset_y = self.scvoffset_y
		self.pv.scvrate = self.scvrate
		self.scv.content_size = (self.image_w*self.scvrate,self.image_h*self.scvrate)#元画像を入れる枠のサイズ
		
		self.scv.content_offset=(newx,newy)#scv offsetを元の位置に近い位置に移動する。左上基準。
		self.scvoffset_x,self.scvoffset_y = self.scv.content_offset
		self.pv.scvoffset_x = self.scvoffset_x#pvの中に現在のscvoffsetを流し込む。
		self.pv.scvoffset_y = self.scvoffset_y		
		
		self.logp(sender,'zoom_set')
		#titleに画像サイズと倍率を表示
		self.name ='Size:' + str(int(self.image_w)) + ', ' + str(int(self.image_h))+' rate:'+str(self.scvrate)+' '+self.filename1

	#log print
	def logp(self,sender,memo):
		print(str(memo)+' biv.w'+str(self.biv.width)+' h'+str(self.biv.height)+' : offset'+str(self.scv.content_offset)+' rate'+str(self.scvrate)+' rate0:'+str(self.scvrate0))

						
	###############################
#v = epaint()
#v.present('fullscreen')

if __name__ == "__main__":
	epaint('epaint')#filename1を引数にしたい。
