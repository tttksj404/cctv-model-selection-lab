package com.ssafy.eyesonu.admin.dto;


public record AdminUpdateResponse(AdminResponse admin, boolean reauthenticationRequired) {
}
