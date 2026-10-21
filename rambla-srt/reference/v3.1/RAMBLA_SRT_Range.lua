-- RAMBLA STUDIO | SRT RANGE EXPORTER v3.1 | DaVinci Resolve Studio 21
-- Windows + macOS | native Fusion UIManager | read-only subtitle export.
-- Single-column UI by design: no growing horizontal groups or off-screen buttons.
local ok, fatal = pcall(function()
  local r = resolve
  if not r and Resolve then r = Resolve() end
  if not r and fusion and fusion.GetResolve then r = fusion:GetResolve() end
  if not r then error('DaVinci Resolve scripting API non disponibile.') end
  local f = fusion or r:Fusion()
  if not f or not f.UIManager or not bmd then error('Fusion UIManager/UIDispatcher non disponibile.') end
  local ui = f.UIManager
  local disp = bmd.UIDispatcher(ui)

  local c = {
    teal='#55D5D0', bright='#80EEE8', ink='#0A2227',
    text='#F0F5F6', muted='#A0B1BB', bg='#25282F',
    line='#52606B', error='#FF9994'
  }
  local baseInput='QLineEdit { background-color: #1E2630; color: #F0F5F6; border: 1px solid #53616F; border-radius: 7px; padding: 6px 9px; font-size: 12px; } QLineEdit:focus { border: 1px solid #55D5D0; }'
  local primary='QPushButton { background-color: #55D5D0; color: #0A2227; border: 0px; border-radius: 8px; padding: 7px 8px; font-size: 13px; font-weight: 800; } QPushButton:hover { background-color: #80EEE8; } QPushButton:disabled { background-color: #3B5255; color: #8CA5A7; }'
  local secondary='QPushButton { background-color: #343D47; color: #E7F0F3; border: 1px solid #52606B; border-radius: 7px; padding: 6px 7px; font-size: 12px; font-weight: 700; } QPushButton:hover { background-color: #44535D; } QPushButton:disabled { background-color: #2A3038; color: #79848D; }'
  local outline='QPushButton { background-color: #202B31; color: #70E4E0; border: 1px solid #428E90; border-radius: 7px; padding: 6px 7px; font-size: 12px; font-weight: 700; } QPushButton:hover { background-color: #304349; }'
  local tcStyle='color: #F1FAFB; background-color: #1F2A32; border: 1px solid #35454F; border-radius: 7px; font-size: 14px; font-weight: 700; padding: 6px 10px;'
  local labelStyle='color: #55D5D0; font-size: 11px; font-weight: 800;'
  -- Bounds and one-column flow prevent the past UIManager min-width explosion.
  -- Text feedback is intentionally short; never print entire paths in QLabel.
  local win=disp:AddWindow({
      ID='RamblaSRT', WindowTitle='RAMBLA  |  SRT Range Exporter v3.1',
      Geometry={100,44,510,830}, MinimumSize={460,720}, MaximumSize={630,970}
    }, ui:VGroup({Spacing=4, Margin=18}, {
      ui:Label({Text='R  /  RAMBLA STUDIO', Weight=0, StyleSheet=labelStyle}),
      ui:Label({Text='EXPORT MULTI SRT', Weight=0,
        StyleSheet='color: #F1F6F7; font-size: 22px; font-weight: 800;'}),
      ui:Label({Text='Esporta i sottotitoli tra IN e OUT.', Weight=0,
        StyleSheet='color: #A0B1BB; font-size: 12px;'}),
      ui:VGap(8),
      ui:Label({ID='RangeState', Text='VERIFICA INTERVALLO...', Weight=0,
        StyleSheet='color: #FF9994; font-size: 17px; font-weight: 800;'}),
      ui:Label({ID='TimelineInfo', Text='', Weight=0,
        StyleSheet='color: #A0B1BB; font-size: 11px;'}),
      ui:Label({ID='InTC', Text='IN       --:--:--:--', Weight=0, StyleSheet=tcStyle}),
      ui:Label({ID='OutTC', Text='OUT     --:--:--:--', Weight=0, StyleSheet=tcStyle}),
      ui:Label({ID='DurationTC', Text='DURATA  --:--:--:--', Weight=0,
        StyleSheet='color: #55D5D0; background-color: #1F2A32; border: 1px solid #35454F; border-radius: 7px; font-size: 14px; font-weight: 800; padding: 6px 10px;'}),
      ui:Label({ID='RangeInfo', Text='', Weight=0,
        StyleSheet='color: #93A9B5; font-size: 11px;'}),
      ui:VGap(4),
      ui:Label({ID='MultiLabel', Text='MULTI RANGE   /   0 INTERVALLI', Weight=0, StyleSheet=labelStyle}),
      ui:Label({ID='MultiList', Text='Nessun intervallo: export usa IN/OUT attuale.', Weight=0,
        StyleSheet='color: #A0B1BB; font-size: 11px;'}),
      ui:Button({ID='AddRange', Text='+ AGGIUNGI INTERVALLO ATTUALE', Weight=0,
        MinimumSize={400,30}, MaximumSize={440,33}, StyleSheet=primary}),
      ui:Button({ID='UndoRange', Text='RIMUOVI ULTIMO INTERVALLO', Weight=0,
        MinimumSize={400,28}, MaximumSize={440,31}, StyleSheet=outline}),
      ui:Button({ID='ClearRanges', Text='SVUOTA LISTA', Weight=0,
        MinimumSize={400,28}, MaximumSize={440,31}, StyleSheet=secondary}),
      ui:VGap(3),
      ui:Label({Text='CARTELLA DI DESTINAZIONE', Weight=0, StyleSheet=labelStyle}),
      ui:LineEdit({ID='Folder', PlaceholderText='Scegli la cartella...', Weight=0,
        MinimumSize={400,31}, MaximumSize={440,32}, StyleSheet=baseInput}),
      ui:Button({ID='Browse', Text='SFOGLIA CARTELLA', Weight=0,
        MinimumSize={400,29}, MaximumSize={440,32}, StyleSheet=outline}),
      ui:VGap(2),
      ui:Label({Text='NOME FILE  /  OPZIONALE', Weight=0, StyleSheet=labelStyle}),
      ui:LineEdit({ID='FileName', PlaceholderText='Automatico: timeline_IN-OUT.srt', Weight=0,
        MinimumSize={400,31}, MaximumSize={440,32}, StyleSheet=baseInput}),
      ui:VGap(3),
      ui:CheckBox({ID='RealTime', Text='Mantieni timecode originali della timeline',
        Checked=true, Weight=0}),
      ui:Label({ID='ModeInfo', Text='Disattiva per iniziare da 00:00:00,000.', Weight=0,
        StyleSheet='color: #94A8B1; font-size: 11px;'}),
      ui:VGap(4),
      ui:Label({Text='CONTESTO  /  OPZIONALE', Weight=0, StyleSheet=labelStyle}),
      ui:CheckBox({ID='Context', Text='Aggiungi testo completo della timeline in coda', Checked=false, Weight=0}),
      ui:Label({Text='Commenti # per GPT; formato SRT sperimentale.', Weight=0,
        StyleSheet='color: #94A8B1; font-size: 11px;'}),
      ui:VGap(3),
      ui:Button({ID='Refresh', Text='AGGIORNA IN / OUT', Weight=0,
        MinimumSize={400,30}, MaximumSize={440,32}, StyleSheet=outline}),
      ui:Label({ID='Feedback', Text='Imposta I e O sulla timeline.', Weight=0,
        StyleSheet='color: #A9BAC3; font-size: 11px;'}),
      ui:VGap(6),
      ui:Button({ID='Export', Text='EXPORT MULTI SRT', Weight=0,
        MinimumSize={400,39}, MaximumSize={440,42}, StyleSheet=primary}),
      ui:Button({ID='OpenFolder', Text='APRI CARTELLA DI DESTINAZIONE', Enabled=false,
        Weight=0, MinimumSize={400,30}, MaximumSize={440,32}, StyleSheet=secondary}),
      ui:Button({ID='Close', Text='CHIUDI', Weight=0,
        MinimumSize={400,29}, MaximumSize={440,31}, StyleSheet=secondary}),
      ui:Label({Text='RAMBLA STUDIO  /  V3.1  /  RESOLVE 21', Weight=0,
        StyleSheet='color: #7D959F; font-size: 10px;'}),
    })
  )
  local el=win:GetItems()
  local currentTimeline, markIn, markOut, fps, timelineStart, timelineFrameIn, timelineFrameOut
  local lastExportFolder=nil
  local savedRanges={}
  local ownerTimeline=nil

  local function short(text,limit)
    text=tostring(text or '')
    if #text>limit then return text:sub(1,limit-3)..'...' end
    return text
  end
  local function setFeedback(txt,bad)
    el.Feedback.Text=short(txt,70)
    el.Feedback.StyleSheet=bad and 'color: #FF9994; font-size: 11px;'
                                      or 'color: #70E5DA; font-size: 11px;'
  end
  local function prettyFrame(frame,rate,drop)
    frame=math.max(0,math.floor(frame+0.5))
    local nominal=math.floor(rate+0.5)
    if drop and (nominal==30 or nominal==60) then
      local d=(nominal==30) and 2 or 4
      local f10=nominal*60*10-d*9
      local fmin=nominal*60-d
      local tens=math.floor(frame/f10)
      local rem=frame%f10
      local extra=math.max(0,math.floor((rem-d)/fmin))
      frame=frame+d*9*tens+d*extra
    end
    local fr=frame%nominal
    local t=math.floor(frame/nominal)
    return string.format('%02d:%02d:%02d%s%02d',math.floor(t/3600),math.floor(t/60)%60,t%60,drop and ';' or ':',fr)
  end
  local function srtTime(ms)
    ms=math.max(0,math.floor(ms+0.5))
    local seconds=math.floor(ms/1000)
    return string.format('%02d:%02d:%02d,%03d',math.floor(seconds/3600),math.floor(seconds/60)%60,seconds%60,ms%1000)
  end
  local function markRange(marks)
    if type(marks)~='table' then return nil,nil end
    for _,kind in ipairs({'video','audio'}) do
      local m=marks[kind]
      if type(m)=='table' then
        local a,b=tonumber(m['in']),tonumber(m['out'])
        if a and b and b>a then return a,b end
      end
    end
    return nil,nil
  end
  -- Convert a timecode into SRT clock milliseconds. SRT has no drop-frame
  -- separator, so the timeline's timecode origin is expressed as real HH:MM:SS,mmm.
  -- The subsequent offset is computed from actual timeline frame distances.
  local function startTimecodeMs(timeline,rate)
    local raw=tostring(timeline:GetStartTimecode() or '')
    local h,m,s,ff=raw:match('^(%d+):(%d+):(%d+)[:;](%d+)$')
    h,m,s,ff=tonumber(h),tonumber(m),tonumber(s),tonumber(ff)
    if not h or not m or not s or not ff or m>59 or s>59 or ff>=math.floor(rate+0.5) then
      return nil
    end
    return (h*3600+m*60+s)*1000+ff*1000/rate
  end
  local function refresh()
    local pm=r:GetProjectManager()
    local project=pm and pm:GetCurrentProject()
    currentTimeline=project and project:GetCurrentTimeline() or nil
    markIn,markOut,fps,timelineStart,timelineFrameIn,timelineFrameOut=nil,nil,nil,nil,nil,nil
    if currentTimeline then
      local success,marks=pcall(function() return currentTimeline:GetMarkInOut() end)
      if success then markIn,markOut=markRange(marks) end
      fps=tonumber(currentTimeline:GetSetting('timelineFrameRate')) or 24
      timelineStart=tonumber(currentTimeline:GetStartFrame()) or 0
    end
    if not markIn or not markOut or markOut<=markIn then
      el.RangeState.Text='IN - OUT not found'
      el.RangeState.StyleSheet='color: #FF9994; font-size: 17px; font-weight: 800;'
      el.TimelineInfo.Text=currentTimeline and ('TIMELINE / '..short(currentTimeline:GetName(),38)) or 'NESSUNA TIMELINE APERTA'
      el.InTC.Text='IN       --:--:--:--'
      el.OutTC.Text='OUT     --:--:--:--'
      el.DurationTC.Text='DURATA  --:--:--:--'
      el.RangeInfo.Text='Imposta I e O nella pagina Edit.'
      el.Export.Enabled=(#savedRanges>0)
      return false
    end
    -- GetMarkInOut can provide relative offsets; subtitle items use frame IDs.
    local endFrame=tonumber(currentTimeline:GetEndFrame()) or 0
    local relative=(timelineStart>0 and markIn<timelineStart and
                    (markOut<=endFrame-timelineStart or endFrame==0))
    timelineFrameIn=relative and timelineStart+markIn or markIn
    timelineFrameOut=relative and timelineStart+markOut or markOut
    local df=tostring(currentTimeline:GetStartTimecode() or ''):find(';',1,true)~=nil
    el.RangeState.Text='IN / OUT FOUND'
    el.RangeState.StyleSheet='color: #70E5DA; font-size: 17px; font-weight: 800;'
    el.TimelineInfo.Text='TIMELINE / '..short(currentTimeline:GetName(),38)
    el.InTC.Text='IN         '..prettyFrame(timelineFrameIn,fps,df)
    el.OutTC.Text='OUT       '..prettyFrame(timelineFrameOut,fps,df)
    el.DurationTC.Text='DURATA   '..prettyFrame(timelineFrameOut-timelineFrameIn,fps,false)
    el.RangeInfo.Text=string.format('%d frame  /  %.3f fps  /  %.2f secondi',timelineFrameOut-timelineFrameIn,fps,(timelineFrameOut-timelineFrameIn)/fps)
    el.Export.Enabled=true
    return true
  end
  local function updateRangeList()
    el.MultiLabel.Text=string.format('MULTI RANGE   /   %d INTERVALLI',#savedRanges)
    if #savedRanges==0 then
      el.MultiList.Text='Nessun intervallo. Export usa l’IN/OUT corrente.'
    else
      local lines={}
      local df=ownerTimeline and tostring(ownerTimeline:GetStartTimecode() or ''):find(';',1,true)~=nil
      for i,v in ipairs(savedRanges) do
        if i<=4 then
          lines[#lines+1]=string.format('%02d  %s - %s',i,prettyFrame(v.a,v.fps,df),prettyFrame(v.b,v.fps,df))
        end
      end
      if #savedRanges>4 then lines[#lines+1]='... e altri '..(#savedRanges-4)..' intervalli' end
      el.MultiList.Text=table.concat(lines,'\n')
    end
  end
  local function addRange()
    if not refresh() then setFeedback('Imposta prima IN e OUT.',true) return end
    if ownerTimeline and ownerTimeline~=currentTimeline then
      setFeedback('Timeline diversa: svuota prima la lista.',true) return
    end
    ownerTimeline=currentTimeline
    local a,b=timelineFrameIn,timelineFrameOut
    for _,v in ipairs(savedRanges) do
      if v.a==a and v.b==b then setFeedback('Intervallo gia presente.',true) return end
    end
    savedRanges[#savedRanges+1]={a=a,b=b,fps=fps}
    updateRangeList()
    setFeedback('Intervallo aggiunto.',false)
  end
  local function undoRange()
    if #savedRanges==0 then return end
    table.remove(savedRanges)
    if #savedRanges==0 then ownerTimeline=nil end
    updateRangeList()
  end
  local function clearRanges()
    savedRanges={}
    ownerTimeline=nil
    updateRangeList()
    setFeedback('Lista intervalli svuotata.',false)
  end
  local function safeFileName(name)
    if name:find('[\\/]') or name:find('[<>|:*?"\r\n]') or name=='.' or name=='..' then return false end
    return true
  end
  local function autoFileName()
    local timeline=currentTimeline and tostring(currentTimeline:GetName()) or 'Timeline'
    timeline=timeline:gsub('[\\/:*?"<>|]','_'):gsub('%s+','_')
    local df=tostring(currentTimeline:GetStartTimecode() or ''):find(';',1,true)~=nil
    local a=prettyFrame(timelineFrameIn or 0,fps or 24,df):gsub('[:;]','-')
    local b=prettyFrame(timelineFrameOut or 0,fps or 24,df):gsub('[:;]','-')
    return timeline..'_'..a..'_'..b..'.srt'
  end
  local function browse()
    local previous=tostring(el.Folder.Text or '')
    local success,folder=pcall(function() return f:RequestDir(previous~='' and previous or nil) end)
    if not success then setFeedback('Impossibile aprire il selettore cartella.',true) return end
    if folder and tostring(folder)~='' then
      el.Folder.Text=tostring(folder)
      setFeedback('Cartella selezionata.',false)
    end
  end
  local function exportRange()
    -- Previously captured ranges remain stable even when I/O markers change.
    local tl
    local ranges={}
    if #savedRanges>0 then
      tl=ownerTimeline
      local pm=r:GetProjectManager()
      local project=pm and pm:GetCurrentProject()
      local active=project and project:GetCurrentTimeline()
      if active~=tl then setFeedback('Torna alla timeline degli intervalli.',true) return end
      for _,v in ipairs(savedRanges) do ranges[#ranges+1]={a=v.a,b=v.b} end
      fps=tonumber(tl:GetSetting('timelineFrameRate')) or fps or 24
      timelineStart=tonumber(tl:GetStartFrame()) or 0
    else
      if not refresh() then setFeedback('IN - OUT not found.',true) return end
      tl=currentTimeline
      ranges[1]={a=timelineFrameIn,b=timelineFrameOut}
    end
    table.sort(ranges,function(a,b) return a.a<b.a end)
    -- Merge overlapping/touching ranges: no duplicate captions.
    local merged={}
    for _,v in ipairs(ranges) do
      local last=merged[#merged]
      if last and v.a<=last.b then last.b=math.max(last.b,v.b)
      else merged[#merged+1]={a=v.a,b=v.b} end
    end
    local folder=tostring(el.Folder.Text or ''):gsub('^%s+',''):gsub('%s+$','')
    if folder=='' then setFeedback('Seleziona una cartella di destinazione.',true) return end
    local name=tostring(el.FileName.Text or ''):gsub('^%s+',''):gsub('%s+$','')
    if name=='' then
      local safe=tostring(tl:GetName() or 'Timeline'):gsub('[\\/:*?"<>|]','_'):gsub('%s+','_')
      name=safe..'_'..(#savedRanges>0 and 'MULTI' or 'RANGE')..'.srt'
    end
    if not safeFileName(name) then setFeedback('Nome file non valido.',true) return end
    if not name:lower():match('%.srt$') then name=name..'.srt' end
    local sep=package.config:sub(1,1)
    local path=folder:gsub('[/\\]+$','')..sep..name
    local offsetBaseMs=nil
    if el.RealTime.Checked then
      offsetBaseMs=startTimecodeMs(tl,fps)
      if not offsetBaseMs then setFeedback('Timecode iniziale non valido.',true) return end
    end
    local subtitleRows={}
    local allCaptionRows={}
    local tracks=tonumber(tl:GetTrackCount('subtitle')) or 0
    for track=1,tracks do
      local items=tl:GetItemListInTrack('subtitle',track) or {}
      if type(items)~='table' then setFeedback('Lista sottotitoli non leggibile.',true) return end
      local unreadable=0
      for idx,item in pairs(items) do
        if type(idx)=='number' then
          if type(item)=='userdata' or type(item)=='table' then
            local good,st,en,content=pcall(function()
              return tonumber(item:GetStart()),tonumber(item:GetEnd()),tostring(item:GetName() or '')
            end)
            if not good or not st or not en then unreadable=unreadable+1
            elseif en>st and content~='' then
              allCaptionRows[#allCaptionRows+1]={a=st,b=en,content=content,track=track,idx=idx}
              for ri,v in ipairs(merged) do
                if en>v.a and st<v.b then
                  local a,b=math.max(st,v.a),math.min(en,v.b)
                  if b>a then subtitleRows[#subtitleRows+1]={a=a,b=b,content=content,track=track,idx=idx,ri=ri} end
                end
              end
            end
          else unreadable=unreadable+1 end
        end
      end
      if unreadable>0 then setFeedback(string.format('Traccia %d: %d elementi non leggibili.',track,unreadable),true) return end
    end
    if #subtitleRows==0 then setFeedback('Nessun sottotitolo negli intervalli.',true) return end
    local function sortRows(a,b)
      if a.a~=b.a then return a.a<b.a end
      if a.track~=b.track then return a.track<b.track end
      return a.idx<b.idx
    end
    table.sort(subtitleRows,sortRows)
    table.sort(allCaptionRows,sortRows)
    local runningOffset={}
    local elapsed=0
    for i,v in ipairs(merged) do runningOffset[i]=elapsed; elapsed=elapsed+(v.b-v.a) end
    local out={}
    for idx,row in ipairs(subtitleRows) do
      local a,b
      if el.RealTime.Checked then
        a=offsetBaseMs+(row.a-timelineStart)*1000/fps
        b=offsetBaseMs+(row.b-timelineStart)*1000/fps
      else
        local v=merged[row.ri]
        a=(runningOffset[row.ri]+row.a-v.a)*1000/fps
        b=(runningOffset[row.ri]+row.b-v.a)*1000/fps
      end
      out[#out+1]=string.format('%d\r\n%s --> %s\r\n%s\r\n\r\n',idx,srtTime(a),srtTime(b),row.content)
    end
    -- Experimental footer for AI ingestion. These are intentionally NOT SRT cues.
    -- Standard SRT has no comment syntax: consuming software may reject this footer.
    if el.Context.Checked then
      out[#out+1]='\r\n# RAMBLA_CONTEXT_BEGIN\r\n'
      out[#out+1]='# EXPERIMENTAL: metadata for GPT/APP REEL, NOT standard SRT.\r\n'
      out[#out+1]='# Do not generate B-roll for text outside selected intervals.\r\n'
      out[#out+1]='# TIMELINE: '..tostring(tl:GetName() or ''):gsub('[\r\n]',' ')..'\r\n'
      out[#out+1]='# SELECTED_RANGES:\r\n'
      local startMs=startTimecodeMs(tl,fps) or 0
      for i,v in ipairs(merged) do
        out[#out+1]=string.format('# RANGE %d: %s --> %s\r\n',i,srtTime(startMs+(v.a-timelineStart)*1000/fps),srtTime(startMs+(v.b-timelineStart)*1000/fps))
      end
      out[#out+1]='# FULL_TIMELINE_TRANSCRIPT (context only):\r\n'
      for _,row in ipairs(allCaptionRows) do
        local txt=row.content:gsub('[\r\n]+',' / ')
        out[#out+1]=string.format('# [%s] %s\r\n',srtTime(startMs+(row.a-timelineStart)*1000/fps),txt)
      end
      out[#out+1]='# RAMBLA_CONTEXT_END\r\n'
    end
    local fh,why=io.open(path,'wb')
    if not fh then setFeedback('Impossibile scrivere il file.',true) print('[RAMBLA] '..tostring(why)) return end
    local result,reason=fh:write(table.concat(out))
    local closed,closeError=fh:close()
    if not result or not closed then setFeedback('Errore scrittura.',true) print('[RAMBLA] '..tostring(reason or closeError)) return end
    lastExportFolder=folder
    el.OpenFolder.Enabled=true
    setFeedback(string.format('Esportati %d sottotitoli da %d intervalli.',#subtitleRows,#merged),false)
    print('[RAMBLA SRT Range v3.1] Export: '..path)
  end
  local function openFolder()
    if not lastExportFolder then setFeedback('Esporta prima un SRT.',true) return end
    local folder=lastExportFolder
    if folder:find('[\r\n"]') then setFeedback('Percorso cartella non valido.',true) return end
    local command
    if package.config:sub(1,1)=='\\' then
      if folder:find('%%') then setFeedback('Percorso con %% non apribile automaticamente.',true) return end
      command='cmd /c start "" "'..folder..'"'
    else
      command="open '"..folder:gsub("'","'\\''").."'"
    end
    local success,opened=pcall(os.execute,command)
    if not success or opened==false then setFeedback('Impossibile aprire la cartella.',true) end
  end
  win.On.RamblaSRT.Close=function() disp:ExitLoop() end
  win.On.Close.Clicked=function() disp:ExitLoop() end
  win.On.Refresh.Clicked=function() refresh() end
  win.On.AddRange.Clicked=function() addRange() end
  win.On.UndoRange.Clicked=function() undoRange() end
  win.On.ClearRanges.Clicked=function() clearRanges() end
  win.On.Browse.Clicked=function() browse() end
  win.On.OpenFolder.Clicked=function() openFolder() end
  win.On.Export.Clicked=function()
    local success,problem=pcall(exportRange)
    if not success then setFeedback('Errore di esportazione. Vedi console Resolve.',true) print('[RAMBLA] '..tostring(problem)) end
  end
  updateRangeList()
  refresh()
  win:Show()
  disp:RunLoop()
  win:Hide()
end)
if not ok then print('[RAMBLA SRT Range] '..tostring(fatal)) end
