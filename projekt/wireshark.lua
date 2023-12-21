-- PksProtocol protocol
local pks_protocol_proto = Proto("PksProtocol", "Custom Header Protocol")
local fields = pks_protocol_proto.fields

local types = {
    [1] = "Init",
    [2] = "Fin",
    [3] = "OK",
    [4] = "Text",
    [5] = "File",
    [6] = "Accept",
    [7] = "Data",
    [8] = "Done",
    [9] = "Next",
    [10] = "Ping"
}

fields.type = ProtoField.uint8("pks_protocol.type", "Type", base.DEC, types)
fields.length = ProtoField.uint16("pks_protocol.length", "Length", base.DEC)
fields.stream = ProtoField.uint32("pks_protocol.stream", "Stream", base.DEC)
fields.checksum = ProtoField.uint32("pks_protocol.checksum", "Checksum", base.DEC)
fields.id = ProtoField.uint16("pks_protocol.id", "ID", base.DEC)
fields.fragment_id = ProtoField.uint16("pks_protocol.fragment_id", "Fragment", base.DEC)
fields.data = ProtoField.string("pks_protocol.data", "Data", base.ASCII)

function pks_protocol_proto.dissector(buffer, pinfo, tree)
    pinfo.cols.protocol = "PksProtocol"
    local subtree = tree:add(pks_protocol_proto, buffer(), "PKS Protokol")

    local p_type = 0
    local p_length = p_type + 1
    local p_stream = p_length + 2
    local p_checksum = p_stream + 4
    local p_id = p_checksum + 4
    local p_data = p_id + 2

    subtree:add(fields.type, buffer(p_type, 1))
    subtree:add(fields.length, buffer(p_length, 2))
    subtree:add(fields.stream, buffer(p_stream, 4))
    subtree:add(fields.checksum, buffer(p_checksum, 4))

    local type = buffer(p_type, p_length):int()
    local length = buffer(p_length, 2):int()
    local stream = buffer(p_stream, 4):int()
    local id = buffer(p_id, 2):int()
    pinfo.cols.info = ""
        .. "Stream: " .. stream .. (stream % 2 == 0 and "(Server)" or "(Client)") .. ", "
        .. (type == 7 and "Fragment: " or "ID: ") .. id .. ", "
        .. "Len: " .. length .. ", "
        .. (types[type] or "Unknown") .. " (" .. type .. ")"

    if (type == 7) then
        subtree:add(fields.fragment_id, buffer(p_id, 2))
    else
        subtree:add(fields.id, buffer(p_id, 2))
    end

    if (length > 0) then
        subtree:add(fields.data, buffer(p_data, length))
    end
end

DissectorTable.get("udp.port"):add(8080, pks_protocol_proto)
